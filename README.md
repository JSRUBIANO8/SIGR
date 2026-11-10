# SIGR · Sistema Integral de Gestión de Restaurante

![Estado](https://img.shields.io/badge/versi%C3%B3n-1.0.0-16846b) ![Python](https://img.shields.io/badge/Python-3.10%2B-blue)

Proyecto académico de **Gestión Software**, Programa de Ingeniería de Software, **Tecnológica del Oriente**. Autor: **Jhoan Sebastian Rubiano Moscoso**.

Aplicación web ejecutable para gestionar **usuarios, menú, pedidos, reservas, facturación interna, reportes y cierre de caja**. Su propósito es disponer de una versión inicial documentada para establecer una línea base de configuración y gestionar cambios con Git.

## Requisitos
- Python **3.10 o superior** (se recomienda 3.12 o 3.13).
- Navegador web moderno.
- **No necesita pip, Node, paquetes externos ni servidor de base de datos.** Usa SQLite y la biblioteca estándar de Python.

## Inicio rápido (Windows PowerShell)

```powershell
git clone https://github.com/TU_USUARIO/sigr.git
cd sigr
py manage.py init-admin
py server.py
```

> Si descargaste el ZIP en vez de clonar, descomprímelo, abre una terminal dentro de la carpeta **SIGR** y ejecuta solo los dos últimos comandos. En macOS/Linux utiliza `python3` en lugar de `py`.

1. `init-admin` te pedirá correo y contraseña (mínimo 8 caracteres) para la cuenta administradora.
2. Abre **http://127.0.0.1:8000**.
3. Ingresa con las credenciales que acabas de crear.
4. Encontrarás mesas, categorías y seis platos de ejemplo para probar los flujos.

**Importante:** no se envía ninguna contraseña predeterminada y la base de datos local no se sube a Git.

## Módulos y flujo

| Módulo | Funciones | Rol autorizado |
|---|---|---|
| Usuarios | Registrar, listar, activar y desactivar cuentas | Administrador |
| Menú | Consultar platos; administrar categorías, precios y disponibilidad | Consultar: usuarios autenticados; modificar: administrador |
| Pedidos | Registrar pedidos y avanzar estados | Administrador, mesero |
| Reservas | Crear, consultar, completar y cancelar; detectar solapamientos por mesa | Administrador, mesero |
| Facturación | Crear factura interna una vez el pedido está entregado | Administrador, mesero |
| Reportes y caja | Consultar ventas por fecha y realizar cierre diario único | Administrador |
| Panel | Indicadores de pedidos, reservas y ventas | Administrador, mesero |

### Estados

- Pedido: `pendiente → preparando → listo → entregado`; se permite cancelar desde `pendiente` o `preparando`.
- Reserva: `confirmada → completada` o `confirmada → cancelada`.
- Una factura se crea **solo** para un pedido entregado y una sola vez por pedido.
- Precios: enteros en **pesos colombianos (COP)**, sin decimales. Cada pedido conserva el precio del momento de su creación.
- Impuestos: tasa de **0 % únicamente con fines de demostración académica** (configurada en `server.py`). No incorpora cálculo tributario legal ni facturación electrónica ante la DIAN.
- Reservas: para la misma mesa, no se admiten inicios con una diferencia estrictamente inferior a 2 horas; tampoco se permite superar la capacidad de la mesa.
- Cierre de caja: una operación por fecha, no reversible desde la interfaz. Una vez cerrado el día actual, la API bloquea nuevas facturas para esa fecha.

## Estructura del repositorio

```text
SIGR/
├── server.py                  # Servidor HTTP WSGI y endpoints JSON
├── database.py                # Esquema SQLite, índices y datos iniciales
├── security.py                # Hash de contraseñas y tokens
├── manage.py                  # Inicialización y creación de administrador
├── static/
│   ├── index.html             # Interfaz
│   ├── styles.css             # Diseño responsivo
│   └── app.js                 # Lógica frontend y consumo de API
├── tests/
│   └── test_sigr.py           # Pruebas automatizadas
├── docs/
│   ├── ARQUITECTURA.md
│   ├── BASE_DATOS.md
│   ├── DESPLIEGUE.md
│   └── LINEA_BASE.md
├── .github/workflows/tests.yml
├── .gitignore
├── CHANGELOG.md
└── LICENSE.txt
```

La carpeta `data/` se crea automáticamente para la base SQLite y está excluida con `.gitignore`.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

El flujo de GitHub Actions (`.github/workflows/tests.yml`) ejecuta las pruebas en cada push a `main` y pull request. Antes de declarar la línea base aprobada, revisa el resultado del flujo en tu repositorio.

## Git: creación de versión inicial

```bash
git init
git add .
git commit -m "feat: implementar SIGR v1.0.0 y pruebas iniciales"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/sigr.git
git push -u origin main
git rev-parse --short HEAD
```

Crea primero un repositorio vacío en GitHub, sustituye `TU_USUARIO`, y **no ejecutes `git init`** si ya clonaste un repositorio. Conserva el hash que devuelve el último comando: se documentará en `docs/LINEA_BASE.md` y en el taller APA 7, en lugar del hash de ejemplo incluido en la guía docente.

## Seguridad y alcance

Prototipo **académico local**, no producto listo para producción: el servidor WSGI incorporado no está diseñado para tráfico público, no existen recuperación de contraseña, integración de pasarelas de pago, auditoría completa, copias automatizadas, integración DIAN ni despliegue HTTPS integrado. Incluye hashing scrypt con sal, sesiones aleatorias almacenadas como hash, cookies `HttpOnly` y `SameSite=Lax`, token CSRF y control básico de roles. Para ambiente real se requerirán endurecimiento de seguridad, servidor de aplicación, HTTPS, respaldos y cumplimiento normativo.

Licencia: MIT. Consulta [CHANGELOG.md](CHANGELOG.md) y [docs/LINEA_BASE.md](docs/LINEA_BASE.md).
