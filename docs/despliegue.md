# Despliegue — Webcafeína Migrator

Runbook de operación en producción. Stack: WHM/cPanel + AlmaLinux + systemd nativo. **Sin Docker** (ADR-001, confirmado en ADR-030/031).

## 0. Convención de variables

Los scripts en `infra/whm-setup/` y `infra/deploy/` toman estas vars de entorno (default razonable si no se exporta):

| Var | Default | Notas |
|---|---|---|
| `WCM_USER` | `webcafeina` | Usuario sistema sin privilegios root |
| `WCM_APP_DIR` | `/home/webcafeina/migrator` | Checkout del repo |
| `WCM_PORT_API` | `8000` | Uvicorn local |
| `WCM_PORT_DASHBOARD` | `3000` | Next.js standalone local |
| `WCM_WORKER_CONCURRENCY` | `2` | Procesos Celery worker |
| `WCM_DOMAIN_API` | `api.migrator.webcafeina.com` | Vhost API |
| `WCM_DOMAIN_DASHBOARD` | `migrator.webcafeina.com` | Vhost dashboard |
| `WCM_PYTHON_VERSION` | `3.14` | Compila desde fuente |
| `WCM_NODE_VERSION` | `22` | nodesource |
| `WCM_POSTGRES_VERSION` | `16` | pgdg-redhat-repo |

Exporta lo que necesites antes de cualquier script:

```bash
export WCM_DOMAIN_API=api.migrator.webcafeina.com
export WCM_DOMAIN_DASHBOARD=migrator.webcafeina.com
```

## 1. Provisión inicial (1 sola vez)

Como **root**:

```bash
cd /tmp
git clone https://github.com/webcafeina/migrator.git
mv migrator /home/webcafeina/      # ajustar a WCM_APP_DIR si difiere
cd /home/webcafeina/migrator

# 1) Python 3.14 + Node 22 + Redis + Postgres + usuario + swap + fail2ban
sudo bash infra/whm-setup/01-system-prereqs.sh

# 2) DB + pgvector + rol
sudo bash infra/whm-setup/02-database.sh
# → guarda el output: DATABASE_URL / DATABASE_SYNC_URL para .env

# 3) .env inicial (secrets auto-generados)
sudo bash infra/whm-setup/05-init-env.sh
# → edita el .env para rellenar DATABASE_URL, GOOGLE_MAPS_API_KEY, etc.
sudo -u webcafeina vi /home/webcafeina/migrator/.env

# 4) Permisos del checkout
sudo chown -R webcafeina:webcafeina /home/webcafeina/migrator

# 5) Primer deploy (como el usuario WCM_USER)
sudo -u webcafeina bash infra/deploy/deploy.sh main

# 6) systemd units + Nginx vhosts
sudo bash infra/whm-setup/03-install-units.sh
sudo bash infra/whm-setup/04-install-nginx.sh

# 7) Arrancar todo
sudo systemctl start wcm.target
sudo systemctl status wcm.target
```

Comprobación final:

```bash
curl -sI https://migrator.webcafeina.com | head -1   # 200 OK
curl -sI https://api.migrator.webcafeina.com/health  # 200 OK
```

## 2. Actualización (cada release)

Como `webcafeina` (no root):

```bash
sudo -u webcafeina bash /home/webcafeina/migrator/infra/deploy/deploy.sh main
```

El script:
1. Guarda el SHA actual en `.cache/last-deploy-sha` (para rollback).
2. `git fetch && checkout && pull`.
3. Instala deps Python + Node nuevas.
4. Aplica migraciones Alembic.
5. Build del dashboard standalone.
6. Restart de las 4 units.
7. Health check post-deploy.

Si el health check falla, el script sale con código != 0 sin haber tocado el código (las units siguen corriendo con la versión anterior).

## 3. Rollback

```bash
sudo -u webcafeina bash /home/webcafeina/migrator/infra/deploy/rollback.sh
```

Vuelve al SHA guardado en `.cache/last-deploy-sha`. **Cuidado**: no revierte migraciones de DB. Si la última migración Alembic rompió compat, ejecuta a mano:

```bash
cd /home/webcafeina/migrator
venv/bin/alembic -c packages/db-schema/alembic.ini downgrade -1
```

## 4. Sudoers para deploy sin password

El `deploy.sh` necesita `sudo systemctl restart` para las units WCM. Crea `/etc/sudoers.d/wcm-deploy` con visudo:

```
webcafeina ALL=(root) NOPASSWD: /usr/bin/systemctl restart wcm-api.service, /usr/bin/systemctl restart wcm-worker.service, /usr/bin/systemctl restart wcm-beat.service, /usr/bin/systemctl restart wcm-dashboard.service
```

Sin esto, el restart te pedirá password y el deploy desde GitHub Actions fallará.

## 5. Logs

- **journald**: `journalctl -u wcm-api -f` (o `-u wcm-worker`, etc.)
- **Nginx**: `/var/log/nginx/wcm-access.log` + `/var/log/nginx/wcm-error.log`
- **Logtail (Better Stack)**: si configurado en `.env`, todos los logs structlog se envían en background.
- **Sentry**: errores con stack trace en https://sentry.io (tu org → proyectos `migrator-api` / `migrator-worker` / `migrator-dashboard`).

## 6. Métricas

`https://api.migrator.webcafeina.com/metrics` expone formato Prometheus. ACL Nginx restringe acceso (ver `infra/nginx/api.migrator.webcafeina.com.conf`). Para integrar con Grafana Cloud:

1. Añade IP del Grafana Agent al `allow` block en el vhost.
2. Configura en Grafana Agent un job scrape con esa URL.

## 7. Verificación deep de salud

```bash
# Localmente en el servidor
curl -s http://127.0.0.1:8000/health/deep | jq

# Devuelve status overall + por-dependencia (db/redis/r2).
# - "ok": todo bien.
# - "degraded": críticos ok, R2 (opcional) caído.
# - "fail": algún crítico (db/redis) caído.
```

## 8. Backups

- **Postgres**: cron diario con `pg_dump` a `/home/webcafeina/backups/` + rotación 14 días. Configurar con cPanel Backup Manager o el siguiente cron:

```bash
0 3 * * * pg_dump -U webcafeina webcafeina_migrator | gzip > /home/webcafeina/backups/wcm-$(date +\%F).sql.gz && find /home/webcafeina/backups -name 'wcm-*.sql.gz' -mtime +14 -delete
```

- **R2**: Cloudflare lifecycle rules + versioning (configurar en el dashboard de Cloudflare).
- **`.env`**: copia manual cifrada en almacenamiento del equipo. NO está versionada.

## 9. Troubleshooting

| Síntoma | Diagnóstico | Acción |
|---|---|---|
| `wcm-api` no arranca | `journalctl -u wcm-api --since '5min ago'` | Suele ser `.env` con valor inválido o Postgres caído |
| 502 Bad Gateway en Nginx | `systemctl status wcm-api` | Si está down, restart; si no, revisa `/var/log/nginx/wcm-error.log` |
| Celery no consume tareas | `redis-cli -n 1 llen webcafeina` | Si la cola crece y no se procesa, restart worker |
| Migración Alembic falla | `journalctl -u wcm-api` durante deploy | `alembic current` y `alembic history` para diagnóstico |
| Dashboard 500 | Sentry `migrator-dashboard` | Mira la breadcrumb del request |
| /health/deep status=fail | `curl /health/deep` | Mira el `checks` JSON para saber qué dep falla |

## 10. Operaciones programadas (systemd timers / cron)

- **Celery beat** (parte de `wcm-beat.service`): retention sweep diario 03:30 Europe/Madrid.
- **pg_dump** (cron): backup diario 03:00.
- **certbot** / **AutoSSL**: gestionado por cPanel automáticamente.

## 11. Escala (cuando haga falta)

- **API**: subir `--workers` en `wcm-api.service` o añadir un segundo nodo + loadbalancer.
- **Worker**: subir `WCM_WORKER_CONCURRENCY` o lanzar más instancias en otros nodos (todos comparten Redis + Postgres).
- **Beat**: NUNCA escalar a >1. Un solo proceso beat para todo el cluster.
- **DB**: replica de lectura + connection pooler (pgbouncer) cuando QPS > 200.

## 12. Seguridad operativa

- Nunca subir `.env` a git (gitignored).
- Rotar secrets cada 6 meses (`JWT_SECRET`, `SECRET_KEY`, API keys).
- fail2ban activado contra SSH brute force.
- Acceso SSH solo con clave (`PasswordAuthentication=no` en `/etc/ssh/sshd_config`).
- `/metrics` y `/health/deep` solo accesibles desde IPs internas (ACL Nginx).
- Sentry con `send_default_pii=False` (no enviar datos personales).
