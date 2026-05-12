# infra/whm-setup

Scripts shell de provisionamiento inicial del servidor WHM/cPanel.

## Estado

Vacío en Fase 0. Se materializa en **Fase 12 — Infra/Deploy**.

## Scripts previstos

Ejecutar como root en orden numérico:

| Script | Acción |
|---|---|
| `01-system-deps.sh` | Python 3.12, Node 20, pnpm, PostgreSQL 16, Redis, Nginx, build-essential, libwebp |
| `02-postgres-setup.sh` | Crear DB, usuario, extensión pgvector |
| `03-app-user.sh` | Crear usuario `webcafeina` no-root |
| `04-clone-repo.sh` | Clonar desde GitHub a `/opt/webcafeina-migrator` |
| `05-install-deps.sh` | `pip install` y `pnpm install` |
| `06-migrations.sh` | `alembic upgrade head` |
| `07-systemd-units.sh` | Copiar y enable units |
| `08-nginx-config.sh` | Copiar config y reload |
| `09-ssl-cert.sh` | Emitir cert con certbot |
| `10-smoke-test.sh` | Health checks |

## Idempotencia

Cada script se puede re-ejecutar sin romper nada. Comprueba estado antes de actuar.

## Variables de entorno

Los scripts asumen `/etc/webcafeina-migrator/env` (permisos `640 root:webcafeina`) con todas las variables de `.env.example` rellenas.

Ver [STATE.md](../../STATE.md) y [docs/despliegue.md](../../docs/despliegue.md).
