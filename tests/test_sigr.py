"""Pruebas integradas usando WSGI (sin requerir pytest)."""
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

TMP = tempfile.TemporaryDirectory()
os.environ['SIGR_DB_PATH'] = str(Path(TMP.name)/'test.sqlite3')
from database import initialize, transaction, connect
from security import hash_password,verify_password
from server import application

class SIGRTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize()
        with transaction() as db:
            db.execute('INSERT INTO users(name,email,password_hash,role) VALUES (?,?,?,?)',
                       ('Admin','admin@test.local',hash_password('ClaveSegura123'),'administrador'))
            db.execute('INSERT INTO users(name,email,password_hash,role) VALUES (?,?,?,?)',
                       ('Cliente','cliente@test.local',hash_password('ClaveSegura123'),'cliente'))

    def call(self,method,path,payload=None,cookie='',csrf=''):
        body=json.dumps(payload).encode() if payload is not None else b''
        captured={}
        def start(status,headers):captured['status']=int(status.split()[0]);captured['headers']=dict(headers)
        env={'REQUEST_METHOD':method,'PATH_INFO':path.split('?')[0], 'QUERY_STRING':path.partition('?')[2],
             'CONTENT_LENGTH':str(len(body)),'CONTENT_TYPE':'application/json','wsgi.input':io.BytesIO(body),
             'HTTP_COOKIE':cookie,'HTTP_X_CSRF_TOKEN':csrf,'wsgi.url_scheme':'http'}
        output=b''.join(application(env,start))
        response=json.loads(output) if path.startswith('/api/') else output
        return captured['status'],response,captured['headers']

    def login(self,email='admin@test.local'):
        code,resp,headers=self.call('POST','/api/auth/login',{'email':email,'password':'ClaveSegura123'})
        self.assertEqual(code,200)
        return headers['Set-Cookie'].split(';')[0],resp['csrf']

    def test_01_hash_password(self):
        h=hash_password('testpassword')
        self.assertTrue(verify_password('testpassword',h))
        self.assertFalse(verify_password('incorrect',h))

    def test_02_auth_protection(self):
        code,_,_=self.call('GET','/api/orders')
        self.assertEqual(code,401)
        code,_,_=self.call('POST','/api/auth/login',{'email':'admin@test.local','password':'badpass'})
        self.assertEqual(code,401)

    def test_03_role_and_csrf(self):
        cookie,csrf=self.login('cliente@test.local')
        code,_,_=self.call('GET','/api/users',cookie=cookie)
        self.assertEqual(code,403)
        code,_,_=self.call('POST','/api/orders',{'items':[{'dish_id':1,'quantity':1}]},cookie=cookie,csrf=csrf)
        self.assertEqual(code,403)
        admin_cookie,_=self.login()
        code,_,_=self.call('POST','/api/categories',{'name':'Prueba'},cookie=admin_cookie)
        self.assertEqual(code,403)

    def test_04_orders_invoice_and_report(self):
        cookie,csrf=self.login()
        def act(method,path,body=None):return self.call(method,path,body,cookie,csrf)
        code,r,_=act('POST','/api/orders',{'table_id':1,'customer_name':'Ana','items':[{'dish_id':2,'quantity':2},{'dish_id':4,'quantity':1}]})
        self.assertEqual(code,201)
        oid=r['id']
        code,_,_=act('POST','/api/invoices',{'order_id':oid,'payment_method':'efectivo'})
        self.assertEqual(code,409)
        for status in ('preparando','listo','entregado'):
            code,_,_=act('PATCH',f'/api/orders/{oid}/status',{'status':status})
            self.assertEqual(code,200)
        code,r,_=act('POST','/api/invoices',{'order_id':oid,'payment_method':'efectivo'})
        self.assertEqual(code,201)
        self.assertEqual(r['total'],85000)
        code,_,_=act('POST','/api/invoices',{'order_id':oid,'payment_method':'efectivo'})
        self.assertEqual(code,409)
        code,r,_=act('GET','/api/reports/sales?date='+datetime.now().strftime('%Y-%m-%d'))
        self.assertEqual(code,200)
        self.assertGreaterEqual(r['grand_total'],85000)

    def test_05_reservations_conflict_and_capacity(self):
        cookie,csrf=self.login()
        slot=(datetime.now()+timedelta(days=2)).strftime('%Y-%m-%dT18:00')
        p={'customer_name':'María','customer_phone':'3001112233','table_id':2,'party_size':3,'starts_at':slot}
        code,r,_=self.call('POST','/api/reservations',p,cookie,csrf)
        self.assertEqual(code,201)
        code,_,_=self.call('POST','/api/reservations',p,cookie,csrf)
        self.assertEqual(code,409)
        p['table_id']=1;p['party_size']=10
        code,_,_=self.call('POST','/api/reservations',p,cookie,csrf)
        self.assertEqual(code,400)

    def test_06_cash_close_once(self):
        cookie,csrf=self.login()
        day=datetime.now().strftime('%Y-%m-%d')
        code,r,_=self.call('POST','/api/cash/close',{'date':day},cookie,csrf)
        self.assertEqual(code,201)
        code,_,_=self.call('POST','/api/cash/close',{'date':day},cookie,csrf)
        self.assertEqual(code,409)

if __name__=='__main__':unittest.main()
