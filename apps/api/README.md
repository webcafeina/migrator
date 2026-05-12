# apps/api

API HTTP del Webcafeína Migrator basada en **FastAPI**.

## Estado

Vacío en Fase 0. Se materializa en **Fase 5 — API backend**.

## Qué contendrá

- Endpoints REST para el dashboard y la CLI (proyectos, leads, campañas, errores).
- Webhook receiver para ClickUp (sync bidireccional).
- Endpoint de auth (JWT con cookies de sesión).
- Endpoint de opt-out (RGPD).
- Integración con Celery (`apps/worker`) para encolar jobs.
- Plantillas de email en `templates/emails/` con paleta Webcafeína.
- Documentos legales en `legal/` (Fase 9).

## Tecnologías

- FastAPI + uvicorn
- SQLAlchemy 2.x async + asyncpg
- Pydantic v2
- structlog + Sentry
- pytest-asyncio para tests

## Subagentes/skills relacionados

- `orchestrator` (ejecuta jobs encolados aquí)
- `gdpr-compliance` skill (endpoints legales)
- `resend-notifier` skill (notificaciones)

Ver [STATE.md](../../STATE.md) para el cursor de avance.
