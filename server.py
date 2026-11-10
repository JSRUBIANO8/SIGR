"""SIGR: servidor HTTP y API REST, implementados con Python estándar."""
import argparse
import json
import logging
import mimetypes
import os
import re
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from http import HTTPStatus
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from wsgiref.simple_server import make_server

from database import connect, initialize, transaction
from security import hash_password, verify_password, make_token, token_hash, expires_in, utc_now

ROOT = Path(__file__).parent
MAX_BODY = 65536
TAX_RATE = 0  # Demostración: tarifa 0 %. Ajustar normativa tributaria antes de producción.
ROLES = ('administrador', 'mesero', 'cliente')

class APIError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def as_dict(row):
    return dict(row) if row is not None else None

def required(data, key, maxlen=150):
    val = data.get(key)
    if not isinstance(val, str) or not val.strip() or len(val.strip()) > maxlen:
        raise APIError(400, f"Campo obligatorio o inválido: {key}")
    return val.strip()

def positive_int(value, key):
    if isinstance(value,bool):
        raise APIError(400, f"{key} debe ser entero positivo")
    try:
        number = int(value)
        if str(value).strip() != str(number) or number <= 0:
            raise ValueError
        return number
    except (ValueError,TypeError):
        raise APIError(400, f"{key} debe ser entero positivo")

def nonnegative_int(value, key):
    n = positive_int(value, key) if str(value) != '0' else 0
    return n

def flag(value, key):
    if value not in (True,False,0,1):
        raise APIError(400, f"{key} debe ser booleano")
    return int(value)

def get_row(db, table, row_id):
    # Solo nombres de tabla fijos internos, nunca entrada del usuario.
    if table not in ('categories','dishes','restaurant_tables','orders','reservations','users','invoices'):
        raise APIError(500,'Tabla inválida')
    r=db.execute(f"SELECT * FROM {table} WHERE id=?",(row_id,)).fetchone()
    if not r:
        raise APIError(404,'Registro no encontrado')
    return r

def json_response(status, data, headers=None):
    body=json.dumps(data,ensure_ascii=False,default=str).encode('utf-8')
    return status, body, [('Content-Type','application/json; charset=utf-8'),('Cache-Control','no-store')]+(headers or [])

def user_from_request(environ):
    cookie=SimpleCookie()
    try: cookie.load(environ.get('HTTP_COOKIE',''))
    except Exception: return None
    token=cookie.get('sigr_session')
    if not token: return None
    with connect() as db:
        r=db.execute("""SELECT u.id,u.name,u.email,u.role,s.csrf_token FROM sessions s
            JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.active=1""",
            (token_hash(token.value),utc_now())).fetchone()
        return as_dict(r)

def authorize(user, roles=None):
    if not user:
        raise APIError(401,'Inicia sesión para continuar')
    if roles and user['role'] not in roles:
        raise APIError(403,'No tienes permisos para esta operación')

def parse_body(environ):
    try: length=int(environ.get('CONTENT_LENGTH') or 0)
    except ValueError: raise APIError(400,'Tamaño de solicitud inválido')
    if length > MAX_BODY: raise APIError(413,'Solicitud demasiado grande')
    if environ.get('CONTENT_TYPE','').split(';')[0] != 'application/json':
        raise APIError(415,'Se requiere Content-Type: application/json')
    try:
        data=json.loads(environ['wsgi.input'].read(length))
        if not isinstance(data,dict): raise ValueError
        return data
    except (ValueError,UnicodeDecodeError):
        raise APIError(400,'JSON inválido')

def date_of(text):
    try: return date.fromisoformat(text).isoformat()
    except (ValueError,TypeError): raise APIError(400,'Fecha inválida; utiliza AAAA-MM-DD')

def datetime_of(text):
    try:
        dt=datetime.fromisoformat(text)
        if dt.tzinfo is not None: raise ValueError
        return dt.strftime('%Y-%m-%dT%H:%M')
    except (ValueError,TypeError):
        raise APIError(400,'Fecha y hora inválidas')

def route(method,path,query,data,user,environ):
    # Acciones públicas de autenticación
    if path=='/api/health' and method=='GET':
        return 200,{'status':'ok','version':'1.0.0'},[]
    if path=='/api/auth/login' and method=='POST':
        email=required(data,'email').lower()
        password=required(data,'password',200)
        with transaction() as db:
            u=db.execute('SELECT * FROM users WHERE email=? AND active=1',(email,)).fetchone()
            if not u or not verify_password(password,u['password_hash']):
                raise APIError(401,'Credenciales inválidas')
            token=make_token(); csrf=make_token()
            db.execute('INSERT INTO sessions(token_hash,user_id,csrf_token,expires_at) VALUES (?,?,?,?)',
                       (token_hash(token),u['id'],csrf,expires_in()))
        secure='; Secure' if environ.get('wsgi.url_scheme')=='https' else ''
        cookie=f'sigr_session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=86400{secure}'
        return 200,{'user':{'id':u['id'],'name':u['name'],'email':u['email'],'role':u['role']},'csrf':csrf},[('Set-Cookie',cookie)]
    if path=='/api/auth/me' and method=='GET':
        authorize(user)
        return 200,{'user':{k:user[k] for k in ('id','name','email','role')},'csrf':user['csrf_token']},[]
    if path=='/api/auth/logout' and method=='POST':
        authorize(user)
        with transaction() as db:
            token=SimpleCookie(); token.load(environ.get('HTTP_COOKIE',''))
            if token.get('sigr_session'):
                db.execute('DELETE FROM sessions WHERE token_hash=?',(token_hash(token['sigr_session'].value),))
        return 200,{'message':'Sesión cerrada'},[('Set-Cookie','sigr_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0')]

    authorize(user)
    if method not in ('GET','HEAD') and environ.get('HTTP_X_CSRF_TOKEN') != user['csrf_token']:
        raise APIError(403,'Token de seguridad faltante o incorrecto')

    if path=='/api/dashboard' and method=='GET':
        authorize(user,('administrador','mesero'))
        today=date.today().isoformat()
        with connect() as db:
            stats={'pedidos_activos':db.execute("SELECT count(*) FROM orders WHERE status IN ('pendiente','preparando','listo')").fetchone()[0],
                   'reservas_hoy':db.execute("SELECT count(*) FROM reservations WHERE substr(starts_at,1,10)=? AND status='confirmada'",(today,)).fetchone()[0],
                   'ventas_hoy':db.execute("SELECT coalesce(sum(total),0) FROM invoices WHERE substr(created_at,1,10)=?",(today,)).fetchone()[0],
                   'facturas_hoy':db.execute("SELECT count(*) FROM invoices WHERE substr(created_at,1,10)=?",(today,)).fetchone()[0]}
        return 200,stats,[]

    if path=='/api/users':
        authorize(user,('administrador',))
        if method=='GET':
            with connect() as db:
                return 200,{'items':[dict(x) for x in db.execute('SELECT id,name,email,role,active,created_at FROM users ORDER BY id')]},[]
        if method=='POST':
            name=required(data,'name'); email=required(data,'email').lower(); password=required(data,'password',200)
            role=required(data,'role')
            if role not in ROLES or '@' not in email: raise APIError(400,'Correo o rol inválido')
            try:
                with transaction() as db:
                    cur=db.execute('INSERT INTO users(name,email,password_hash,role) VALUES (?,?,?,?)',(name,email,hash_password(password),role))
                return 201,{'id':cur.lastrowid,'message':'Usuario creado'},[]
            except sqlite3.IntegrityError: raise APIError(409,'El correo ya existe')
    m=re.fullmatch(r'/api/users/(\d+)',path)
    if m and method=='PATCH':
        authorize(user,('administrador',)); uid=int(m[1]); active=flag(data.get('active'),'active')
        if uid==user['id'] and not active: raise APIError(409,'No puedes desactivar tu propio usuario')
        with transaction() as db:
            get_row(db,'users',uid)
            db.execute('UPDATE users SET active=? WHERE id=?',(active,uid))
            if not active: db.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
        return 200,{'message':'Usuario actualizado'},[]

    if path=='/api/categories':
        if method=='GET':
            with connect() as db:
                return 200,{'items':[dict(r) for r in db.execute('SELECT * FROM categories ORDER BY name')]},[]
        if method=='POST':
            authorize(user,('administrador',))
            try:
                with transaction() as db: cur=db.execute('INSERT INTO categories(name) VALUES (?)',(required(data,'name'),))
                return 201,{'id':cur.lastrowid},[]
            except sqlite3.IntegrityError: raise APIError(409,'Categoría duplicada')
    m=re.fullmatch(r'/api/categories/(\d+)',path)
    if m and method=='PUT':
        authorize(user,('administrador',))
        try:
            with transaction() as db:
                get_row(db,'categories',int(m[1]))
                db.execute('UPDATE categories SET name=?,active=? WHERE id=?',(required(data,'name'),flag(data.get('active'),'active'),int(m[1])))
            return 200,{'message':'Categoría actualizada'},[]
        except sqlite3.IntegrityError: raise APIError(409,'Categoría duplicada')

    if path=='/api/dishes':
        if method=='GET':
            with connect() as db:
                rows=db.execute('SELECT d.*,c.name category FROM dishes d JOIN categories c ON c.id=d.category_id ORDER BY c.name,d.name')
                return 200,{'items':[dict(x) for x in rows]},[]
        if method=='POST':
            authorize(user,('administrador',))
            category_id=positive_int(data.get('category_id'),'category_id')
            price=nonnegative_int(data.get('price'),'price')
            with transaction() as db:
                get_row(db,'categories',category_id)
                cur=db.execute('INSERT INTO dishes(category_id,name,description,price,available) VALUES (?,?,?,?,?)',
                              (category_id,required(data,'name'),str(data.get('description',''))[:500],price,flag(data.get('available',True),'available')))
            return 201,{'id':cur.lastrowid},[]
    m=re.fullmatch(r'/api/dishes/(\d+)',path)
    if m and method=='PUT':
        authorize(user,('administrador',))
        with transaction() as db:
            get_row(db,'dishes',int(m[1])); category_id=positive_int(data.get('category_id'),'category_id')
            get_row(db,'categories',category_id)
            db.execute('UPDATE dishes SET name=?,description=?,category_id=?,price=?,available=? WHERE id=?',
                       (required(data,'name'),str(data.get('description',''))[:500],category_id,
                        nonnegative_int(data.get('price'),'price'),flag(data.get('available'),'available'),int(m[1])))
        return 200,{'message':'Plato actualizado'},[]
    if m and method=='DELETE':
        authorize(user,('administrador',))
        with transaction() as db:
            get_row(db,'dishes',int(m[1]))
            # Borrado lógico: preserva historial, evita ruptura de pedidos.
            db.execute('UPDATE dishes SET available=0 WHERE id=?',(int(m[1]),))
        return 200,{'message':'Plato desactivado'},[]

    if path=='/api/tables' and method=='GET':
        with connect() as db:
            return 200,{'items':[dict(x) for x in db.execute('SELECT * FROM restaurant_tables ORDER BY id')]},[]

    if path=='/api/reservations':
        authorize(user,('administrador','mesero'))
        if method=='GET':
            with connect() as db:
                rows=db.execute('SELECT r.*,t.label table_name FROM reservations r JOIN restaurant_tables t ON t.id=r.table_id ORDER BY r.starts_at DESC LIMIT 300')
                return 200,{'items':[dict(x) for x in rows]},[]
        if method=='POST':
            table_id=positive_int(data.get('table_id'),'table_id'); party_size=positive_int(data.get('party_size'),'party_size')
            starts_at=datetime_of(data.get('starts_at'))
            if datetime.fromisoformat(starts_at) < datetime.now(): raise APIError(400,'La reserva debe ser futura')
            with transaction() as db:
                table=get_row(db,'restaurant_tables',table_id)
                if party_size>table['capacity']: raise APIError(400,'La mesa no tiene capacidad suficiente')
                # Se reserva un bloque de 2 horas alrededor del inicio, para impedir solapamientos.
                dt=datetime.fromisoformat(starts_at)
                lower=(dt-timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M')
                upper=(dt+timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M')
                if db.execute("SELECT 1 FROM reservations WHERE table_id=? AND status='confirmada' AND starts_at>? AND starts_at<?",(table_id,lower,upper)).fetchone():
                    raise APIError(409,'La mesa ya tiene reserva dentro del intervalo de 2 horas')
                cur=db.execute('INSERT INTO reservations(customer_name,customer_phone,table_id,starts_at,party_size,created_by) VALUES (?,?,?,?,?,?)',
                        (required(data,'customer_name'),required(data,'customer_phone',30),table_id,starts_at,party_size,user['id']))
            return 201,{'id':cur.lastrowid},[]
    m=re.fullmatch(r'/api/reservations/(\d+)/status',path)
    if m and method=='PATCH':
        authorize(user,('administrador','mesero'))
        status=required(data,'status')
        if status not in ('cancelada','completada'): raise APIError(400,'Estado inválido')
        with transaction() as db:
            r=get_row(db,'reservations',int(m[1]))
            if r['status']!='confirmada': raise APIError(409,'Esta reserva ya está finalizada')
            db.execute('UPDATE reservations SET status=? WHERE id=?',(status,int(m[1])))
        return 200,{'message':'Reserva actualizada'},[]

    if path=='/api/orders':
        authorize(user,('administrador','mesero'))
        if method=='GET':
            with connect() as db:
                orders=[dict(x) for x in db.execute('SELECT o.*,t.label table_name FROM orders o LEFT JOIN restaurant_tables t ON t.id=o.table_id ORDER BY o.id DESC LIMIT 200')]
                for o in orders:
                    o['items']=[dict(x) for x in db.execute('SELECT dish_id,dish_name,unit_price,quantity FROM order_items WHERE order_id=?',(o['id'],))]
                    o['total']=sum(x['unit_price']*x['quantity'] for x in o['items'])
                    o['invoiced']=bool(db.execute('SELECT 1 FROM invoices WHERE order_id=?',(o['id'],)).fetchone())
                return 200,{'items':orders},[]
        if method=='POST':
            items=data.get('items')
            if not isinstance(items,list) or not items or len(items)>50: raise APIError(400,'Agrega entre 1 y 50 ítems')
            table_id=data.get('table_id')
            if table_id is not None: table_id=positive_int(table_id,'table_id')
            with transaction() as db:
                if table_id: get_row(db,'restaurant_tables',table_id)
                prepared=[]
                for item in items:
                    if not isinstance(item,dict): raise APIError(400,'Ítem inválido')
                    dish=get_row(db,'dishes',positive_int(item.get('dish_id'),'dish_id'))
                    if not dish['available']: raise APIError(409,f"Plato no disponible: {dish['name']}")
                    qty=positive_int(item.get('quantity'),'quantity')
                    if qty>100: raise APIError(400,'Máximo 100 unidades por ítem')
                    prepared.append((dish['id'],dish['name'],dish['price'],qty))
                cur=db.execute('INSERT INTO orders(table_id,customer_name,created_by) VALUES (?,?,?)',
                               (table_id,str(data.get('customer_name',''))[:100],user['id']))
                db.executemany('INSERT INTO order_items(order_id,dish_id,dish_name,unit_price,quantity) VALUES (?,?,?,?,?)',
                               [(cur.lastrowid,*item) for item in prepared])
            return 201,{'id':cur.lastrowid,'message':'Pedido creado'},[]
    m=re.fullmatch(r'/api/orders/(\d+)/status',path)
    if m and method=='PATCH':
        authorize(user,('administrador','mesero'))
        status=required(data,'status')
        transitions={'pendiente':('preparando','cancelado'),'preparando':('listo','cancelado'),'listo':('entregado',),'entregado':(),'cancelado':()}
        with transaction() as db:
            order=get_row(db,'orders',int(m[1]))
            if status not in transitions[order['status']]: raise APIError(409,'Transición de pedido no permitida')
            db.execute('UPDATE orders SET status=? WHERE id=?',(status,int(m[1])))
        return 200,{'message':'Estado actualizado'},[]

    if path=='/api/invoices':
        authorize(user,('administrador','mesero'))
        if method=='GET':
            with connect() as db:
                return 200,{'items':[dict(r) for r in db.execute('SELECT * FROM invoices ORDER BY id DESC LIMIT 300')]},[]
        if method=='POST':
            order_id=positive_int(data.get('order_id'),'order_id'); methodpay=required(data,'payment_method')
            if methodpay not in ('efectivo','tarjeta','transferencia'): raise APIError(400,'Método de pago inválido')
            with transaction() as db:
                order=get_row(db,'orders',order_id)
                if order['status']!='entregado': raise APIError(409,'Solo se facturan pedidos entregados')
                if db.execute('SELECT 1 FROM invoices WHERE order_id=?',(order_id,)).fetchone():
                    raise APIError(409,'Este pedido ya tiene factura')
                if db.execute('SELECT 1 FROM cash_closures WHERE business_date=?',(date.today().isoformat(),)).fetchone():
                    raise APIError(409,'La caja del día está cerrada; no se permiten nuevas facturas')
                total=db.execute('SELECT sum(unit_price*quantity) FROM order_items WHERE order_id=?',(order_id,)).fetchone()[0]
                subtotal=total; tax=(subtotal*TAX_RATE)//100; total=subtotal+tax
                cur=db.execute('INSERT INTO invoices(order_id,subtotal,tax,total,payment_method,created_by) VALUES (?,?,?,?,?,?)',
                               (order_id,subtotal,tax,total,methodpay,user['id']))
            return 201,{'id':cur.lastrowid,'total':total},[]

    if path=='/api/reports/sales' and method=='GET':
        authorize(user,('administrador',))
        business_date=date_of(query.get('date',[date.today().isoformat()])[0])
        with connect() as db:
            rows=[dict(r) for r in db.execute('SELECT id,order_id,total,payment_method,created_at FROM invoices WHERE substr(created_at,1,10)=? ORDER BY id',(business_date,))]
            totals={pay:sum(x['total'] for x in rows if x['payment_method']==pay) for pay in ('efectivo','tarjeta','transferencia')}
            closure=as_dict(db.execute('SELECT * FROM cash_closures WHERE business_date=?',(business_date,)).fetchone())
        return 200,{'date':business_date,'items':rows,'totals':totals,'grand_total':sum(totals.values()),'invoice_count':len(rows),'closure':closure},[]
    if path=='/api/cash/close' and method=='POST':
        authorize(user,('administrador',))
        business_date=date_of(data.get('date'))
        if business_date>date.today().isoformat(): raise APIError(400,'No se puede cerrar una fecha futura')
        with transaction() as db:
            if db.execute('SELECT 1 FROM cash_closures WHERE business_date=?',(business_date,)).fetchone():
                raise APIError(409,'La caja ya está cerrada para esta fecha')
            rows=db.execute('SELECT total,payment_method FROM invoices WHERE substr(created_at,1,10)=?',(business_date,)).fetchall()
            totals={pay:sum(r['total'] for r in rows if r['payment_method']==pay) for pay in ('efectivo','tarjeta','transferencia')}
            cur=db.execute('INSERT INTO cash_closures(business_date,cash_total,card_total,transfer_total,grand_total,invoice_count,closed_by) VALUES (?,?,?,?,?,?,?)',
                (business_date,totals['efectivo'],totals['tarjeta'],totals['transferencia'],sum(totals.values()),len(rows),user['id']))
        return 201,{'id':cur.lastrowid,'total':sum(totals.values()),'message':'Cierre realizado'},[]

    raise APIError(404,'Ruta no encontrada')


def application(environ,start_response):
    method=environ.get('REQUEST_METHOD','GET').upper()
    path=urlparse(environ.get('PATH_INFO','/')).path
    try:
        if not path.startswith('/api/'):
            if method!='GET': raise APIError(405,'Método no permitido')
            safe={'/':'index.html','/index.html':'index.html','/styles.css':'styles.css','/app.js':'app.js'}
            filename=safe.get(path)
            if not filename: raise APIError(404,'Archivo no encontrado')
            body=(ROOT/'static'/filename).read_bytes()
            mime=mimetypes.guess_type(filename)[0] or 'application/octet-stream'
            status,headers=200,[('Content-Type',mime+'; charset=utf-8'),('X-Content-Type-Options','nosniff')]
        else:
            user=user_from_request(environ)
            data=parse_body(environ) if method in ('POST','PUT','PATCH') else {}
            query=parse_qs(environ.get('QUERY_STRING',''))
            status,result,extra=route(method,path,query,data,user,environ)
            status,body,headers=json_response(status,result,extra)
    except APIError as exc:
        status,body,headers=json_response(exc.status,{'error':exc.message})
    except sqlite3.IntegrityError:
        status,body,headers=json_response(409,{'error':'Conflicto de datos; verifica la información'})
    except Exception:
        logging.exception('Error interno')
        status,body,headers=json_response(500,{'error':'Error interno del servidor'})
    headers += [('Content-Length',str(len(body))),('X-Frame-Options','DENY'),('Referrer-Policy','same-origin')]
    start_response(f'{status} {HTTPStatus(status).phrase}',headers)
    return [body]


def main():
    parser=argparse.ArgumentParser(description='Servidor local SIGR')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8000)
    args=parser.parse_args()
    initialize()
    with connect() as db:
        has_admin=db.execute("SELECT 1 FROM users WHERE role='administrador'").fetchone()
    if not has_admin:
        print('No hay administrador. Ejecuta antes: python manage.py init-admin')
        return
    logging.basicConfig(level=logging.INFO)
    with make_server(args.host,args.port,application) as server:
        print(f'SIGR disponible en http://{args.host}:{args.port}')
        server.serve_forever()

if __name__=='__main__': main()
