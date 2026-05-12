# Despliegue — Webcafeína Migrator

> Documento stub. Se completa en **Fase 12 — Infra/Deploy**.

---

## Stack de despliegue

- **WHM/cPanel** con acceso SSH root
- **Sin Docker** ([ADR-001](./decisiones.md#adr-001))
- Procesos nativos gestionados por **systemd**
- **Nginx** como reverse proxy
- **PostgreSQL 16** + extensión `pgvector`
- **Redis 7**
- **Python 3.12** en venv aislado
- **Node 20+** con pnpm 9+
- **Certbot** para SSL (Let's Encrypt)

## Provisionamiento inicial

Scripts en `infra/whm-setup/`:

```
01-system-deps.sh        Python 3.12, Node 20, pnpm, PostgreSQL 16, Redis, Nginx, libwebp
02-postgres-setup.sh     DB + usuario + pgvector
03-app-user.sh           usuario webcafeina no-root
04-clone-repo.sh         clonar a /opt/webcafeina-migrator
05-install-deps.sh       pip + pnpm install
06-migrations.sh         alembic upgrade head
07-systemd-units.sh      copiar + enable units
08-nginx-config.sh       copiar config + reload
09-ssl-cert.sh           certbot
10-smoke-test.sh         health checks
```

Idempotentes — re-ejecutables sin romper nada.

## Servicios systemd

- `webcafeina-api.service` (uvicorn FastAPI en 127.0.0.1:8000)
- `webcafeina-worker.service` (Celery worker, concurrency=4)
- `webcafeina-beat.service` (Celery Beat scheduler)
- `webcafeina-dashboard.service` (Next.js standalone en 127.0.0.1:3000)

Hardening: `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `ReadWritePaths` restringido.

Ver skill [systemd-service-generator](../.claude/skills/systemd-service-generator/SKILL.md).

## Variables de entorno

Fichero `/etc/webcafeina-migrator/env` con permisos `640 root:webcafeina`.

Contenido basado en [`.env.example`](../.env.example) con los valores reales rellenos.

Variables sensibles obligatorias (validar en `01-system-deps.sh`):
- `DATABASE_URL`, `REDIS_URL`
- `SECRET_KEY`, `JWT_SECRET`
- `RESEND_API_KEY`, `SENTRY_DSN_*`
- (Producción) `BRIGHTDATA_*`, `TWOCAPTCHA_API_KEY`, `R2_*`
- `CLICKUP_API_TOKEN`

## Despliegue continuo

GitHub Actions workflow `.github/workflows/deploy-{staging,production}.yml`:

1. Trigger: merge a `develop` (staging) o tag `v*.*.*` en `main` (producción)
2. SSH al servidor con clave deploy
3. Ejecutar `infra/deploy/deploy.sh`
4. Smoke test
5. Notificación Resend a `nacho@webcafeina.com`

## SSL

Certbot:
```bash
certbot --nginx -d migrator.webcafeina.com --email info@webcafeina.com --agree-tos
```

Renovación automática vía cron de certbot (default sistema).

## Backups

(Por documentar en Fase 12)
- Postgres: `pg_dump` diario a `/var/backups/webcafeina-migrator/` + sync a R2.
- Redis: snapshots cada 6h (RDB).
- Assets R2: ya redundantes en Cloudflare (multi-region).

## Monitoreo

- **Health**: `GET /health` (FastAPI) y `GET /` (dashboard) — pingdom o uptime-kuma externo.
- **Errores**: Sentry alerts a `nacho@webcafeina.com`.
- **Logs**: Logtail dashboard.
- **Métricas operacionales**: dashboard interno `/`.

## Recuperación ante incidentes

(Por documentar en Fase 15 — Hardening)
- RTO target: 1 h
- RPO target: 24 h (backup diario)
- Runbook: `docs/runbook-incidentes.md` (a crear)

---

## Por documentar a medida que avanzamos

- Detalles concretos del distro WHM (CentOS, AlmaLinux, RHEL — confirmar versión)
- Plan de migración entre servidores
- Procedimiento de rotación de secretos
