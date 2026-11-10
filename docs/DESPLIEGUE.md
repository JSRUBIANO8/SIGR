# Manual de despliegue local — SIGR

1. Instalar Python 3.10 o superior y confirmar `python --version` (Windows puede usar `py --version`).
2. Descargar o clonar el repositorio y abrir la terminal en la carpeta raíz `SIGR`.
3. Opcional: `python manage.py init-db` (también lo ejecuta `init-admin`).
4. Crear un usuario administrador con `python manage.py init-admin`. Se solicitarán correo y contraseña.
5. Ejecutar `python server.py`.
6. Abrir `http://127.0.0.1:8000`.
7. Iniciar sesión, crear un pedido, avanzar a `entregado`, emitir factura y consultar reporte.
8. Detener con `Ctrl+C`.

Para cambiar el puerto: `python server.py --port 8080`.

**Problemas frecuentes:**
- `python: command not found`: instala Python o usa `py`/`python3`.
- "No hay administrador": ejecuta `python manage.py init-admin`.
- "Address already in use": utiliza otro puerto.
- Si olvidaste la contraseña de la única cuenta administradora, restaura una copia de la base de datos o reinicia el prototipo local eliminando `data/sigr.sqlite3` **solo si no necesitas conservar sus datos**.

**Pruebas:** `python -m unittest discover -s tests -v`.

**Seguridad:** la configuración predeterminada escucha solo en `127.0.0.1`. No publicar el servidor WSGI de desarrollo en Internet. No subir `data/` al repositorio. Para despliegue de producción se necesita revisión de seguridad, HTTPS, backups, servidor adecuado y manejo de datos personales.
