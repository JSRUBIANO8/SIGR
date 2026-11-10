"""Persistencia SQLite y esquema inicial del SIGR (sin dependencias externas)."""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.getenv("SIGR_DB_PATH", str(Path(__file__).parent / "data" / "sigr.sqlite3")))

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL,
 email TEXT NOT NULL UNIQUE COLLATE NOCASE,
 password_hash TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('administrador','mesero','cliente')),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 csrf_token TEXT NOT NULL,
 expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS categories (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL UNIQUE,
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
);
CREATE TABLE IF NOT EXISTS dishes (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 category_id INTEGER NOT NULL REFERENCES categories(id),
 name TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '',
 price INTEGER NOT NULL CHECK(price>=0),
 available INTEGER NOT NULL DEFAULT 1 CHECK(available IN (0,1))
);
CREATE TABLE IF NOT EXISTS restaurant_tables (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 label TEXT NOT NULL UNIQUE,
 capacity INTEGER NOT NULL CHECK(capacity>0)
);
CREATE TABLE IF NOT EXISTS reservations (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 customer_name TEXT NOT NULL,
 customer_phone TEXT NOT NULL,
 table_id INTEGER NOT NULL REFERENCES restaurant_tables(id),
 starts_at TEXT NOT NULL,
 party_size INTEGER NOT NULL CHECK(party_size>0),
 status TEXT NOT NULL DEFAULT 'confirmada' CHECK(status IN ('confirmada','cancelada','completada')),
 created_by INTEGER NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS orders (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 table_id INTEGER REFERENCES restaurant_tables(id),
 customer_name TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'pendiente' CHECK(status IN ('pendiente','preparando','listo','entregado','cancelado')),
 created_by INTEGER NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS order_items (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 order_id INTEGER NOT NULL REFERENCES orders(id),
 dish_id INTEGER NOT NULL REFERENCES dishes(id),
 dish_name TEXT NOT NULL,
 unit_price INTEGER NOT NULL CHECK(unit_price>=0),
 quantity INTEGER NOT NULL CHECK(quantity>0)
);
CREATE TABLE IF NOT EXISTS invoices (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
 subtotal INTEGER NOT NULL CHECK(subtotal>=0),
 tax INTEGER NOT NULL CHECK(tax>=0),
 total INTEGER NOT NULL CHECK(total>=0),
 payment_method TEXT NOT NULL CHECK(payment_method IN ('efectivo','tarjeta','transferencia')),
 created_by INTEGER NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS cash_closures (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 business_date TEXT NOT NULL UNIQUE,
 cash_total INTEGER NOT NULL,
 card_total INTEGER NOT NULL,
 transfer_total INTEGER NOT NULL,
 grand_total INTEGER NOT NULL,
 invoice_count INTEGER NOT NULL,
 closed_by INTEGER NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_reservations_slot ON reservations(table_id, starts_at, status);
CREATE INDEX IF NOT EXISTS ix_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS ix_invoices_created ON invoices(created_at);
"""

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=10000")
    return db

@contextmanager
def transaction():
    db = connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def initialize():
    with connect() as db:
        db.executescript(SCHEMA)
        if not db.execute("SELECT 1 FROM categories").fetchone():
            db.executemany("INSERT INTO categories(name) VALUES (?)", [(n,) for n in ("Entradas","Platos fuertes","Bebidas","Postres")])
        if not db.execute("SELECT 1 FROM restaurant_tables").fetchone():
            db.executemany("INSERT INTO restaurant_tables(label,capacity) VALUES (?,?)", [(f"Mesa {i}",4 if i<5 else 6) for i in range(1,9)])
        if not db.execute("SELECT 1 FROM dishes").fetchone():
            db.executemany("INSERT INTO dishes(category_id,name,description,price) VALUES (?,?,?,?)", [
                (1,"Patacones con hogao","Entrada tradicional",14000),
                (2,"Bandeja paisa","Especial de la casa",38000),
                (2,"Pechuga a la plancha","Con acompañamiento",32000),
                (3,"Limonada natural","Vaso de 400 ml",9000),
                (3,"Jugo de mora","Preparado en agua",8500),
                (4,"Postre de tres leches","Porción individual",13000)])
