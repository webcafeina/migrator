# apps/worker

Procesos Celery del Webcafeína Migrator. Ejecutan los pipelines de prospección y migración.

## Estado

Vacío en Fase 0. Se materializa en **Fase 6 — Worker + subagentes**.

## Qué contendrá

- App Celery configurada con Redis broker.
- Tasks que envuelven cada subagente (`tasks/orchestrator.py`, `tasks/scraper_origin.py`, etc.).
- Schedules en Beat (Celery Beat) para jobs periódicos:
  - `purge_expired_leads` (semanal)
  - `refresh_campaigns` (diario)
  - `reconcile_clickup_status` (cada 6h)
  - `fingerprint_recheck` (mensual)
- Manejo de retries por error tipado.
- Hooks de Sentry + structlog.

## Servicios systemd asociados

- `webcafeina-worker.service` (worker)
- `webcafeina-beat.service` (beat scheduler)

Generados por `deployer-systemd` agente / `systemd-service-generator` skill.

Ver [STATE.md](../../STATE.md).
