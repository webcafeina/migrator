# apps/api

API HTTP del Webcafeína Migrator basada en **FastAPI**.

## Estado

Materializado en **Fase 5**. 32 rutas. 33 tests unit con dependency override (sin Postgres real).

## Estructura

```
src/wcm_api/
├── main.py              # FastAPI app + lifespan + montaje de routers
├── config.py            # ApiSettings (pydantic-settings) leyendo .env
├── db/session.py        # async engine + session dependency
├── security.py          # JWT + cookies + argon2 + dependencies de auth
├── errors.py            # ApiError + register_error_handlers (envelope JSON)
├── tasks/
│   ├── celery_app.py    # app Celery compartida con worker (Fase 6)
│   └── enqueue.py       # send_task helpers (sin lógica)
└── routers/
    ├── health.py        # /health + /ready (sin auth)
    ├── opt_out.py       # /opt-out RGPD (público, HTML)
    ├── auth.py          # /api/v1/auth/{login,logout,me}
    ├── users.py         # /api/v1/users (admin only)
    ├── leads.py         # /api/v1/leads (read all, write operator+)
    ├── campaigns.py     # /api/v1/campaigns/launch
    ├── projects.py      # /api/v1/projects + start/resume/cancel/phases
    ├── residual_tasks.py# /api/v1/residual-tasks (con sync ClickUp)
    ├── errors.py        # /api/v1/errors (lectura error_log)
    └── webhooks.py      # /api/v1/webhooks/clickup (HMAC)
```

## API endpoints (32 rutas registradas)

| Categoría | Rutas |
|---|---|
| Probes | `GET /health`, `GET /ready` |
| RGPD | `GET /opt-out` (público, HTML) |
| Auth | `POST /api/v1/auth/login`, `/logout`, `GET /auth/me` |
| Users | `GET/POST /api/v1/users`, `GET/DELETE /users/{id}` (admin) |
| Leads | `GET/PATCH /api/v1/leads`, `POST /leads/{id}/refingerprint` |
| Campaigns | `POST /api/v1/campaigns/launch` (encola Celery) |
| Projects | `GET/POST/PATCH`, `POST /start /resume /cancel`, `GET /phases` |
| Residual | `GET /api/v1/residual-tasks`, `PATCH /{id}/status` |
| Errors | `GET /api/v1/errors` (filtros severity, component, project) |
| Webhooks | `POST /api/v1/webhooks/clickup` (HMAC SHA-256) |
| Docs | `/docs` (Swagger UI), `/redoc`, `/openapi.json` |

## Arrancar localmente

```bash
# venv con paquetes instalados
source .venv/bin/activate

# variables del repo
set -a; source .env; set +a

# Asegurar que Postgres + Redis están corriendo localmente
uvicorn wcm_api.main:app --reload --port 8000
# → http://localhost:8000/docs
```

## Autenticación

- **Dashboard**: cookie http-only `wcm_session` (set por `/auth/login`)
- **CLI / scripts**: header `Authorization: Bearer <token>` o `x-wcm-token: <token>`

Roles (de `wcm_types.enums.UserRole`):
- `admin` — todo
- `operator` — crear/editar leads, proyectos, campañas; NO gestión de usuarios
- `viewer` — solo lectura

## Errores

Respuesta JSON con envelope estable:
```json
{"error": {"code": "not_found", "message": "Project 42 no encontrado", "details": {}}}
```

En desarrollo (`ENV=development`), `details.stack` lleva las últimas 12 líneas del traceback para debug. En producción se omite.

Mapping automático para errores de paquetes:
- `WpAuthError` → 502 + `wp_upstream_auth`
- `WpRateLimitError` → 502 + `wp_upstream_rate_limit`
- `WpBulkPartialError` → 207 + `wp_bulk_partial`
- `BricksTranspileError` → 500 + `bricks_transpile_error`

## Tests

```bash
# Unit con mocks (sin red, sin DB, sin Redis):
pytest apps/api -q

# Todo el repo:
set -a; source .env; set +a
pytest packages apps -q
```

Fixtures principales en `tests/conftest.py`:
- `client` — `httpx.AsyncClient(ASGITransport(app))` sin red real
- `fake_session` — `AsyncSession` mockeada con `AsyncMock`
- `admin_token` / `operator_token` / `viewer_token` — JWT firmados por rol

## Pendiente (post-Fase 5)

- Integración Sentry + structlog (Fase 11)
- Rate limiting en `/opt-out` y `/auth/login` (Fase 15 hardening)
- `/api/v1/scraped-pages` y `/api/v1/bricks-pages` (lectura para debug del pipeline, Fase 6 o 8)
- WebSocket para timeline en vivo del proyecto (Fase 8 si el dashboard lo necesita)

## ADRs relacionados

- ADR-019 — Versionado `/api/v1/...` + endpoint público RGPD fuera del prefijo
