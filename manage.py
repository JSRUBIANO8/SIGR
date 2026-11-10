"""Comandos de inicialización y administración del sistema."""
import argparse
import getpass
import sqlite3
from database import initialize, transaction
from security import hash_password

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['init-db','init-admin'])
    parser.add_argument('--name',default='Administrador SIGR')
    parser.add_argument('--email')
    args=parser.parse_args()
    initialize()
    if args.command=='init-db':
        print('Base de datos inicializada con categorías, mesas y menú de ejemplo.')
        return
    email=args.email or input('Correo administrador: ').strip()
    password=getpass.getpass('Contraseña (mínimo 8 caracteres): ')
    confirm=getpass.getpass('Repetir contraseña: ')
    if password != confirm:
        print('Las contraseñas no coinciden.'); return
    try:
        with transaction() as db:
            db.execute('INSERT INTO users(name,email,password_hash,role) VALUES (?,?,?,?)',
                       (args.name,email.lower(),hash_password(password),'administrador'))
        print('Administrador creado. Ahora ejecuta: python server.py')
    except (sqlite3.IntegrityError,ValueError) as e:
        print(f'No fue posible crear el administrador: {e}')

if __name__=='__main__': main()
