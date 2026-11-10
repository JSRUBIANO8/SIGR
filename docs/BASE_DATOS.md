# Diccionario de datos — SIGR v1.0.0

Base de datos SQLite inicializada mediante `database.py`. Cada tabla usa una clave primaria, salvo `sessions` cuyo identificador es `token_hash`.

| Tabla | Propósito | Campos clave y relaciones |
|---|---|---|
| `users` | Cuentas y roles | `email` único, `password_hash`, `role`, `active` |
| `sessions` | Sesiones | `token_hash` PK, `user_id → users`, `csrf_token`, `expires_at` |
| `categories` | Categorías de menú | `name` único, `active` |
| `dishes` | Platos | `category_id → categories`, `name`, `price`, `available` |
| `restaurant_tables` | Mesas físicas | `label` único, `capacity` |
| `reservations` | Agenda de mesas | `table_id → restaurant_tables`, `starts_at`, `party_size`, `status`, `created_by → users` |
| `orders` | Encabezados de pedidos | `table_id → restaurant_tables` (opcional), `status`, `created_by → users` |
| `order_items` | Detalle de pedido | `order_id → orders`, `dish_id → dishes`, `dish_name`, `unit_price`, `quantity` |
| `invoices` | Facturas internas | `order_id → orders` único, `subtotal`, `tax`, `total`, `payment_method` |
| `cash_closures` | Cierres de caja | `business_date` único, totales por medio de pago, `closed_by → users` |

## Relaciones

- Un usuario puede generar múltiples pedidos, reservas y facturas.
- Una categoría tiene varios platos; un plato puede aparecer en varios detalles de pedido.
- Cada pedido tiene uno o más ítems, y **máximo una factura**.
- Una mesa puede tener múltiples reservas no solapadas y múltiples pedidos.
- Cada fecha comercial puede tener **un cierre**.

El archivo `database.py` es la definición normativa del esquema y sus restricciones, y los datos iniciales son ejemplos académicos. Los archivos `data/*.sqlite3` deben mantenerse fuera del repositorio.
