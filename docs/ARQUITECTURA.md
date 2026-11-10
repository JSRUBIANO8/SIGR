# Arquitectura técnica — SIGR v1.0.0

## Estilo
Monolito web educativo de tres capas, dependencias exclusivamente estándar de Python:

```text
Navegador (HTML + CSS + JavaScript)
  │ HTTP JSON + cookie de sesión + X-CSRF-Token
  ▼
server.py (WSGI / REST + validaciones + permisos)
  ├── security.py (scrypt, tokens, expiración)
  └── database.py (SQLite y transacciones)
        ▼
    data/sigr.sqlite3 (datos persistentes locales)
```

## Endpoints (resumen)

| Método | Ruta | Uso |
|---|---|---|
| GET | `/api/health` | Salud del servidor |
| POST | `/api/auth/login` | Inicio de sesión |
| GET / POST | `/api/auth/me`, `/api/auth/logout` | Sesión |
| GET / POST | `/api/users` | Listado / alta usuario |
| PATCH | `/api/users/{id}` | Activación/desactivación |
| GET / POST | `/api/categories` | Categorías |
| PUT | `/api/categories/{id}` | Editar categoría |
| GET / POST | `/api/dishes` | Platos |
| PUT / DELETE | `/api/dishes/{id}` | Editar / desactivar plato |
| GET | `/api/tables` | Mesas |
| GET / POST | `/api/reservations` | Reservas |
| PATCH | `/api/reservations/{id}/status` | Estado de reserva |
| GET / POST | `/api/orders` | Pedidos |
| PATCH | `/api/orders/{id}/status` | Estado de pedido |
| GET / POST | `/api/invoices` | Facturas internas |
| GET | `/api/reports/sales?date=AAAA-MM-DD` | Reporte diario |
| POST | `/api/cash/close` | Cierre de caja |

## Reglas de negocio y consistencia

- Se utilizan transacciones `BEGIN IMMEDIATE` en operaciones con riesgos de concurrencia (creación de reserva, factura y cierre).
- Los precios unitarios se copian a los ítems del pedido para conservar el histórico.
- La relación `invoices.order_id` tiene restricción `UNIQUE` para evitar dobles facturas.
- Roles separados: administrador, mesero, cliente. La API controla permisos independientemente de la interfaz.
- Las entradas SQL usan parámetros. El frontend escapa valores al insertarlos en HTML.
- Se usan sesiones con expiración de un día y tokens CSRF para mutaciones.

## Limitaciones académicas

No hay API pública de cliente, integración externa, notificaciones, impuestos reales, comprobantes fiscales o control de turnos. El servidor usa hora local del equipo. Las reservas asumen ocupación fija de dos horas sin validación de horario comercial. La facturación usa un modelo simplificado para evaluar control de versiones.
