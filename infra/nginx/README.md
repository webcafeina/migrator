# infra/nginx

Configs Nginx para Webcafeína Migrator. **Sin Docker** — Nginx nativo en WHM/cPanel.

## Estado

Vacío en Fase 0. Se materializa en **Fase 12 — Infra/Deploy**.

## Ficheros previstos

- `webcafeina-migrator.conf` — vhost principal:
  - `443` con SSL (Let's Encrypt via certbot)
  - Redirect `80 → 443`
  - Reverse proxy `/api/ → 127.0.0.1:8000` (FastAPI)
  - Reverse proxy `/ → 127.0.0.1:3000` (Next standalone)
  - `client_max_body_size 50M` para uploads
  - Headers de seguridad estándar

Se instala con `infra/whm-setup/08-nginx-config.sh`.

Ver [STATE.md](../../STATE.md).
