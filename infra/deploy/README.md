# infra/deploy

Scripts de despliegue idempotente sobre el servidor de producción/staging.

## Estado

Vacío en Fase 0. Se materializa en **Fase 12 — Infra/Deploy**.

## Ficheros previstos

- `deploy.sh` — pipeline idempotente:
  1. `git pull` en `/opt/webcafeina-migrator`
  2. `pip install -e .` actualizado
  3. `pnpm install` y `pnpm build` (dashboard)
  4. `alembic upgrade head`
  5. `systemctl restart webcafeina-{api,worker,beat,dashboard}`
  6. Smoke test (curl health)
- `rollback.sh` — vuelve al commit anterior + redeploys

Triggered desde GitHub Actions (`.github/workflows/deploy-{staging,production}.yml`).

Ver [STATE.md](../../STATE.md).
