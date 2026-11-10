# Acta propuesta de línea base de configuración — SIGR

| Campo | Valor |
|---|---|
| Identificador | LB-SIGR-001 |
| Versión propuesta | 1.0.0 |
| Fecha de documentación | 09/11/2026 |
| Responsable académico | Jhoan Sebastian Rubiano Moscoso |
| Curso | Gestión Software |
| Rama estable | `main` (una vez publicada) |
| URL de repositorio | **Pendiente: completar con URL real de GitHub** |
| Commit de referencia | **Pendiente: copiar resultado de `git rev-parse --short HEAD`** |
| Estado | **Candidata, pendiente de validación y aprobación del grupo** |

## Elementos de configuración incluidos

Código backend: `server.py`, `database.py`, `security.py`, `manage.py`. Interfaz: `static/`. Validación: `tests/`. Integración continua: `.github/workflows/tests.yml`. Documentación: `README.md`, `CHANGELOG.md`, `docs/`, `LICENSE.txt`. Exclusiones: `.gitignore`.

## Lista de verificación para aprobación

- [ ] El código se encuentra en la rama principal `main` del repositorio del estudiante.
- [ ] Se registra el hash real del último commit estable.
- [ ] `python -m unittest discover -s tests -v` finaliza sin fallos en el equipo y en GitHub Actions.
- [ ] Se ejecuta `python server.py` y se verifica el acceso desde navegador.
- [ ] Se prueban login, CRUD de menú, pedido, reserva, facturación y cierre de caja.
- [ ] Los responsables revisan y aprueban el alcance y las limitaciones documentadas.
- [ ] Se crea la etiqueta Git `v1.0.0` sobre el commit aprobado.

## Registro de cambios posterior a la línea base

Toda solicitud deberá incluir identificador (GitHub Issue), descripción, motivación, impacto, responsable, aprobación, rama de trabajo, pull request, prueba y commit. Las modificaciones a `main` se integrarán tras revisión y pruebas. Las nuevas versiones utilizarán versionado semántico (MAJOR.MINOR.PATCH).

> El hash `a93b4f1` y la ruta `github.com/equipoX/sigr` de la guía del curso son **ejemplos**, no se declaran como evidencia real de este repositorio.
