# STATE.md — Cursor de avance Webcafeína Migrator

> Este fichero se actualiza al final de cada sesión de construcción.
> Lo lee Claude al iniciar cada nueva sesión para retomar exactamente donde quedó.

---

## Fase actual

- **Fase 0 — Bootstrap**: ✅ Completada (commit `f7aa1a7`)
- **Fase 1 — DB y modelos**: ✅ Completada (commit `3ad2b7b`)
- **Fase 2 — Bricks transpiler**: ✅ Completada (commit `d653557`)
- **Fase 3 — Scraper core**: ✅ Completada (commit `01c93d4`)
- **Fase 4 — WP client**: ✅ Completada (commit `db21bf6`)
- **Fase 5 — API backend**: ✅ Completada (commit `fb6bcc5`)
- **Fase 6 — Worker + subagentes operativos**: ✅ Completada (commit `5c1767d`)
- **Fase 7 — CLI**: ✅ Completada (commit `0d3b528`)
- **Fase 8 — Dashboard**: ✅ Completada (commit `17944a2`)
- **Fase 9 — Prospección**: ✅ Completada (commit `34bb07d`)
- **Fase 10 — Integraciones externas**: ✅ Completada (commit `e46d5ce`)
- **Fase 11 — Observabilidad**: ✅ Completada (commit `3863daa`)
- **Fase 12 — Infra/Deploy**: ✅ Completada esta sesión
- **Próxima fase**: Fase 13 — Tests e2e (Playwright para dashboard + flujo migración completo + CI matrix)

---

## Tabla de progreso

| Fase | Nombre | Estado | Notas |
|---|---|---|---|
| 0 | Bootstrap | ✅ Completada | Estructura + agentes + skills + memoria |
| 1 | DB y modelos | ✅ Completada | 17 tablas, migración 0001, pydantic schemas, tipos TS auto |
| 2 | Bricks transpiler | ✅ Completada | Esquema observacional v1, 16 mappers, validador, theme styles, 63 tests |
| 3 | Scraper core | ✅ Completada | Playwright wrapper + 3 extractors + proxy layered free→paid (ADR-017) + sidecar Puppeteer + 57 tests |
| 4 | WP client | ✅ Completada | REST + WP-CLI vía paramiko + workarounds Local (ADR-018) + 29 tests (21 unit + 8 integración contra sandbox real WP 6.9.4) |
| 5 | API backend | ✅ Completada | FastAPI con 32 rutas + JWT + cookies + RBAC + opt-out RGPD + webhooks HMAC + 33 tests con dependency override |
| 6 | Worker + subagentes | ✅ Completada | Orchestrator + 8 subagentes REAL + 11 STUB + 4 Celery tasks + 28 tests (ADR-020 separa descriptors .md de runtime .py) |
| 7 | CLI | ✅ Completada | Typer + Rich, doble entrypoint webcafeina-migrator/wcm, 11 grupos de comandos, CliError=ClickException (ADR-021), 17 tests |
| 8 | Dashboard | ✅ Completada | Next.js 15 + shadcn/ui + JetBrains Mono (ADR-022) + paleta WCM estricta + 10 páginas + 15 tests Vitest |
| 9 | Prospección | ✅ Completada | GooglePlacesClient (legacy, ADR-024) + ProspectorAgent + EnricherAgent con embedding e5-large (ADR-023) + OutreachComposer LSSI-CE + 4 docs legales + 268 tests Python (+38 nuevos) |
| 10 | Integraciones externas | ✅ Completada | ClickUp/Resend/R2 clients (ADR-025/26/27) + ClickupSyncer + ResendNotifier + OutreachSender + AssetOptimizer (Pillow→WebP) + retention sweep (Celery beat) + webhook Resend + 325 tests Python (+57 nuevos) |
| 11 | Observabilidad | ✅ Completada | structlog + Sentry (api/worker/dashboard) + Logtail + Prometheus `/metrics` + `/health/deep` (db/redis/r2) — todo perezoso (ADR-028/29). 25 tests nuevos. Total 350+15. |
| 12 | Infra/Deploy | ✅ Completada | 4 systemd units + target + Nginx vhosts + 5 scripts WHM setup + 4 scripts deploy + 2 workflows GitHub Actions + runbook completo en docs/despliegue.md (ADR-030/031). 29 tests validación. Total 379+15. |
| 13 | Tests e2e | ⏳ Pendiente | |
| 14 | Documentación | ⏳ Pendiente | |
| 15 | Hardening | ⏳ Pendiente | |

---

## Tareas completadas en la última sesión (Fase 12)

- [x] **`infra/systemd/`** — 4 unit files + target agregado (ADR-030):
  - `wcm-api.service` (uvicorn, 2 workers, hardening completo)
  - `wcm-worker.service` (celery, concurrency configurable, TimeoutStopSec=120s)
  - `wcm-beat.service` (único en el cluster)
  - `wcm-dashboard.service` (Next.js standalone)
  - `wcm.target` (agrega las 4)
  - `uvicorn-log.json` (log config externo)
  - Hardening: NoNewPrivileges, ProtectSystem=strict, PrivateTmp, ProtectKernelTunables/Modules/ControlGroups, RestrictAddressFamilies, LockPersonality, SystemCallFilter=@system-service, ReadWritePaths explícito.
- [x] **`infra/nginx/`** — 3 ficheros:
  - `wcm-common.conf` (snippet con HSTS, CSP, X-Frame-Options, TLS 1.2/1.3, gzip)
  - `api.migrator.webcafeina.com.conf` (reverse proxy + ACL `/metrics` y `/health/deep` con `deny all`)
  - `migrator.webcafeina.com.conf` (dashboard standalone + cache largo en /_next/static)
- [x] **`infra/whm-setup/`** — 5 scripts (idempotentes, `set -euo pipefail`):
  - `00-env.sh` (variables compartidas: WCM_USER, WCM_APP_DIR, puertos, dominios)
  - `01-system-prereqs.sh` (Python 3.14 desde fuente, Node 22, Redis, Postgres+pgvector, user sistema, swap si <2GB, fail2ban)
  - `02-database.sh` (DB + rol + pgvector, password auto-generada)
  - `03-install-units.sh` (envsubst + systemctl daemon-reload + enable)
  - `04-install-nginx.sh` (envsubst + `nginx -t` + reload)
  - `05-init-env.sh` (genera `.env` desde example con secrets aleatorios, modo 600)
- [x] **`infra/deploy/`** — 4 scripts:
  - `deploy.sh` (guarda SHA previo, pull, deps Python+Node, migrate, build dashboard, restart, health-check)
  - `rollback.sh` (vuelve al SHA anterior)
  - `migrate.sh` (alembic upgrade head)
  - `health-check.sh` (curl /health + /ready + /health/deep + jq al status, falla con exit 1 si "fail")
- [x] **`.github/workflows/`** — 2 workflows (listos pero inactivos hasta push del repo, ADR-013):
  - `ci.yml` — 3 jobs (python con services Postgres+Redis+pgvector / typescript / infra validación)
  - `deploy-production.yml` — manual SSH trigger con appleboy/ssh-action
- [x] **`docs/despliegue.md`** runbook completo: provisión inicial → primer deploy → updates → rollback → sudoers → logs → métricas → backups → troubleshooting → escala → seguridad operativa.
- [x] **29 tests de validación infra** en `tests/unit/test_infra.py`: `bash -n` para 13 scripts, secciones críticas en 5 systemd units, hardening directives, headers de seguridad en Nginx, ACL en `/metrics` y `/health/deep`, YAML parseable en workflows, ejecutabilidad de scripts, `set -euo pipefail` presente en críticos.
- [x] **ADR-030** (systemd nativo + 4 units + target) y **ADR-031** (single-server WHM topology).
- [x] Fix YAML en `ci.yml`: bloque Python heredoc reemplazado por grep simple para no romper `yaml.safe_load`.
- [x] Total: **379 Python + 15 TS = 394 tests** pasando.

## Tareas completadas en sesión anterior (Fase 11)

- [x] **structlog central** en API y worker (`apps/{api,worker}/src/.../observability/logging_config.py`): JSON renderer en prod, ConsoleRenderer (sin colores) en dev. Stdlib `logging` puenteado para que libs externas (uvicorn, sqlalchemy, httpx) emitan también JSON. Silencia `httpx`/`botocore`/`urllib3` a WARNING. Idempotente.
- [x] **Sentry SDK** integrado en 3 componentes (ADR-028):
  - API: `FastApiIntegration` + `StarletteIntegration` + `SqlalchemyIntegration`.
  - Worker: `CeleryIntegration(monitor_beat_tasks=True)` + `SqlalchemyIntegration`.
  - Dashboard: `@sentry/nextjs@^9.0.0` con `sentry.client.config.ts`, `sentry.server.config.ts`, `sentry.edge.config.ts` + `instrumentation.ts` (Next 15).
  - Todos perezosos: sin DSN, no se inicializan.
  - PII off por defecto (`send_default_pii=False`).
- [x] **Logtail (Better Stack)** handler opcional via `LOGTAIL_SOURCE_TOKEN`. Sin token = no-op.
- [x] **Métricas Prometheus** (ADR-029) en registry propio (no global) para evitar contaminación entre tests:
  - API: `wcm_http_requests_total{method,path,status}` y `wcm_http_request_duration_seconds{method,path}` vía middleware Starlette.
  - Worker: `wcm_celery_tasks_total{task,status}`, `wcm_celery_task_duration_seconds{task}`, `wcm_agent_runs_total{agent,status}`, `wcm_agent_run_duration_seconds{agent}` instrumentadas via Celery signals.
  - Endpoint `GET /metrics` en API (sin auth, formato OpenMetrics, `text/plain`).
  - Cardinalidad controlada: `path` toma plantilla resuelta (`/projects/{id}`) o fallback truncado a 4 segmentos.
- [x] **`/health/deep`** verifica Postgres (`SELECT 1`), Redis (`PING` con timeout 2s), R2 (`head_bucket`). Devuelve por-dependencia: `ok` | `fail` | `skipped`. Overall `ok` si críticos ok, `degraded` si solo opcionales fallan, `fail` si algún crítico falla. Útil para diagnóstico runbook y dashboards.
- [x] **25 tests nuevos** Python (12 observability API, 5 /health/deep, 2 /metrics endpoint, 6 observability worker). Total **350 Python + 15 TS**.
- [x] **2 ADRs**: ADR-028 (observabilidad), ADR-029 (Prometheus).
- [x] **Deps añadidas**:
  - Python: `sentry-sdk[fastapi,celery]>=2.0`, `prometheus-client`, `logtail-python`.
  - JS: `@sentry/nextjs@^9.0.0`.
- [x] Test renombrado `test_observability.py` → `test_worker_observability.py` en worker para evitar colisión con el de la API (pytest no admite duplicate basenames en la misma run).

## Tareas completadas en sesión anterior (Fase 10)

- [x] **Clientes de integración** en `apps/worker/src/wcm_worker/integrations/`:
  - `ClickupClient` (REST v2, retry exponencial sobre 429/5xx, no retry sobre 4xx)
  - `ResendClient` (wrapper SDK oficial, validador HMAC para webhooks, `from_env()` perezoso)
  - `R2Client` (boto3 S3-compat apuntando a `<account>.r2.cloudflarestorage.com`, ADR-026)
- [x] **ClickupSyncerAgent real**: crea/actualiza/cierra tareas según `residual_tasks` del proyecto. Mapeo de prioridades por categoría. Tag `wcm-residual-<id>` para join inverso (ADR-027). Sin token devuelve `skipped` sin romper el pipeline.
- [x] **ResendNotifierAgent real**: notificaciones internas (`@webcafeina.com` only) con guarda anti-leak. Sin API key → skip.
- [x] **OutreachSenderAgent nuevo**: envía un `OutreachSend` concreto vía Resend. Doble-check anti-spam contra `opt_out_log` justo antes del envío. Promueve la `OutreachSequence` de READY a IN_PROGRESS en el primer envío exitoso. Persiste `provider_message_id` y `sent_at`. AuditLog `SEND` con `legal_ground=6.1.f`.
- [x] **AssetOptimizerAgent real**: descarga assets pendientes del proyecto, sniff por magic bytes, re-encode a WebP con Pillow (quality 82, strip metadata), sube a R2 con key `wcm/projects/{pid}/{hash[:2]}/{hash}.webp`. Sin credenciales R2 deja en `OPTIMIZED`; el siguiente run lo termina.
- [x] **Celery tasks**:
  - `wcm.outreach.send_step` (delega en OutreachSender)
  - `wcm.maintenance.retention_sweep` (purga leads DISCOVERED >12m sin outreach, OUTREACH_SENT>24m→DISCARDED→borrar +6m, error_log >90d)
  - `wcm.clickup.sync_residuals` actualizado a real
  - **Celery beat** schedule añadido: retention_sweep diario a las 03:30 Europe/Madrid
- [x] **Endpoint** `POST /api/v1/outreach/sequences/{id}/send` (with optional `step_index`).
- [x] **Webhook entrante** `POST /api/v1/webhooks/resend` con verificación HMAC sobre body crudo. Eventos `email.sent/delivered/opened/bounced/complained` actualizan el `OutreachSend.{status,sent_at,opened_at,bounced_at}` con regla "no retrocedemos" (`_highest_status`).
- [x] **Tests**: 57 nuevos (10 integraciones, 8 ClickupSyncer, 10 OutreachSender, 8 AssetOptimizer, 5 ResendNotifier, 8 endpoints/webhook Fase 10, 5 retention sweep, 3 ajustes en `test_agents_stubs`). Total **325 Python + 15 TS**.
- [x] **3 ADRs**: ADR-025 (Resend), ADR-026 (R2 vía boto3), ADR-027 (sync ClickUp con `clickup_task_id`).
- [x] **Deps añadidas** a `apps/worker/pyproject.toml`: `boto3>=1.40`, `resend>=2.0`, `Pillow>=11.0`.
- [x] **`.env.example`** ampliado con `RESEND_WEBHOOK_SECRET`.
- [x] Stubs Fase 10 retirados de `test_agents_stubs.py` (Clickup/Resend/Asset son reales ahora).
- [x] **WCM-006 cerrado parcialmente**: cron de purga implementado; queda añadir columna `retention_hold` para excepciones AEPD (WCM-013 nueva).

## Tareas completadas en sesión anterior (Fase 9)

- [x] **EmbeddingService** (`apps/worker/src/wcm_worker/embedding.py`): singleton lazy con `sentence-transformers` + `intfloat/multilingual-e5-large` (1024 dim), LRU cache, prefijos `passage:` / `query:` según convención e5. **100% gratuito**, sin API externa.
- [x] **GooglePlacesClient** (`packages/scraper-core/src/wcm_scraper_core/directories/google_places.py`): cliente Places API **legacy** (ADR-024, la API key del proyecto no tiene Places New), Text Search + Place Details, field mask reducido, caché 7 días, retry 429/503 sin retry en REQUEST_DENIED, error tipado `GooglePlacesQuotaExceeded`. Cache key sanea `api_key` para no filtrar el secret.
- [x] **ProspectorAgent real**: sustituye el stub. Construye query `{sector} en {region}`, itera resultados Google, filtra (no_website, blocked_types, exclude_domains), upsert con `ON CONFLICT DO NOTHING`, persiste `LeadEnrichment` + `AuditLog DISCOVER` con `legal_ground=6.1.f`.
- [x] **EnricherAgent ampliado**: además de emails/teléfonos/socials, calcula embedding 1024-dim del texto del lead (business_name + sector + region + builder + snippet HTML). Defensivo: si sentence-transformers no está instalado o el modelo falla, registra `embedding.computed=False` y continúa sin bloquear el enrichment. AuditLog ENRICH añadido.
- [x] **OutreachComposerAgent real**: plantillas Jinja2 (`wix_intro_es`, `followup_es`) en `apps/worker/src/wcm_worker/templates/outreach/`. Persiste `OutreachSequence` (status `DRAFT_PENDING_REVIEW`) + `OutreachSend` por paso. Validador legal v1.0 verifica razón social + CIF + dirección + URL opt-out en cada body. Aborta si el lead está en `opt_out_log` previo.
- [x] **4 documentos legales** en `apps/api/legal/`: `tratamiento_datos_prospeccion.md` (art. 6.1.f RGPD + 21.2 LSSI-CE), `plantilla_aviso_legal_outreach.md`, `politica_retencion.md`, `procedimiento_brecha.md` (72h notificación AEPD).
- [x] **Endpoints API nuevos**:
  - `POST /api/v1/leads/{id}/opt-out-url` → genera URL firmada (JWT opt-out)
  - `POST /api/v1/leads/{id}/consent` → registro manual de objection/manual_review en audit_log
  - `POST /api/v1/leads/{id}/outreach/compose` → encola OutreachComposerAgent
  - `GET /api/v1/outreach/sequences` (lista) + `/{id}` (detalle con sends)
  - `POST /api/v1/outreach/sequences/{id}/transition` (approve/pause/cancel con validaciones)
- [x] **Task Celery** `wcm.outreach.compose_for_lead` + helper `enqueue_outreach_compose` en API.
- [x] **38 tests nuevos**: 10 GooglePlacesClient (con httpx MockTransport), 11 ProspectorAgent, 12 OutreachComposerAgent (incluyendo validación legal), 7 EnricherAgent embedding, 12 endpoints API.
- [x] **Total repo: 268 tests Python pasan + 15 TS** (era 227+15, +41 nuevos Python).
- [x] **ADR-023** sentence-transformers + e5-large (supersede ADR-010 Voyage AI).
- [x] **ADR-024** Places API legacy vs New.
- [x] Datos legales reales integrados en `.env` (CIF B10463990, dirección Santa Cristina s/n Edif. Embarcadero 10195 Cáceres, URL privacidad con trailing slash).
- [x] WCM-002 cerrado (datos legales completos).
- [x] Stubs `ProspectorAgent` + `OutreachComposerAgent` retirados de `test_agents_stubs.py`.

## Tareas completadas en sesión anterior (Fase 8)

- [x] Paquete `apps/dashboard/` con Next.js 15.0 + React 19 + TypeScript 5.6 + Tailwind 3.4 + shadcn/ui
- [x] Tipografía **JetBrains Mono** en toda la UI (ADR-022) via `next/font/google` con weights 400/500/600/700
- [x] Paleta Webcafeína estricta en `tailwind.config.ts` con tokens `wcm-*` + aliases shadcn-compatibles
- [x] 7 componentes UI customizados: Button, Input, Label, Card (+ subparts), Table (+ subparts), Badge (con `statusVariant()` para mapping del dominio), Skeleton
- [x] Componentes layout: Sidebar con icons lucide-react + nav items + indicador activo, Header con `/auth/me` + LogoutButton
- [x] **10 páginas funcionales**:
  - `/login` form email+password
  - `/` overview con 4 métricas + proyectos activos + errores recientes
  - `/leads` tabla densa con filtros (sector/region/builder/status/min-score)
  - `/leads/[id]` detalle con 4 cards (identificación, fingerprint, contacto, evidencia JSON) + RefingerprintButton
  - `/projects` listado con badges de status
  - `/projects/[id]` detalle + ProjectActions (start/resume/cancel) + timeline de fases
  - `/projects/[id]/checklist` agrupado por categoría (blocking_go_live → post_go_live)
  - `/projects/[id]/diff` placeholder con explicación de Fase 10
  - `/campaigns` form launch + notas legales
  - `/errors` tabla del error_log con filtros severity/component/project
  - `/residual-tasks` tabla con MarkDoneButton (encola sync ClickUp)
  - `/settings` user info + instrucciones SSH para editar `.env`
- [x] `lib/api.ts` cliente fetch con cookie `credentials: "include"` + mapping del error envelope JSON → `ApiError` con `status` + `code` + `details`
- [x] `middleware.ts` redirige a `/login?from=<path>` si no hay cookie `wcm_session`. Excluye `/api/*`, `/login`, `/_next/*`, `/opt-out`
- [x] `next.config.mjs` con rewrites `/api/v1/*` → `${API_URL}/api/v1/*` (evita CORS en dev) + `output: "standalone"` para systemd (Fase 12)
- [x] `pnpm install` exitoso (582 paquetes resueltos en 21.2s) — incluye workspace deps
- [x] **Tests Vitest 15/15 passan** (cn, formatDate, truncate, ApiError shape, statusVariant para 10 estados del dominio)
- [x] **`tsc --noEmit` pasa sin errores** con strict + noUncheckedIndexedAccess
- [x] ADR-022 (JetBrains Mono en toda la UI)
- [x] Total repo: **227 Python + 15 TS = 242 tests passan**

## Tareas completadas en sesión anterior (Fase 7)

- [x] Paquete `cli/` con Typer 0.12 + Rich 13.8 + httpx 0.27
- [x] Dos entrypoints registrados: `webcafeina-migrator` (oficial) + `wcm` (alias). Ambos apuntan a `wcm_cli.main:main`
- [x] `config.py` con `CliConfig.load()` que autocarga `.env` del cwd + cache de credenciales en `~/.config/wcm/credentials.json` (modo 600)
- [x] `errors.py`: `CliError` hereda de `click.ClickException` con `show()` override a stdout (excepto modo `--json`). Sub-errores: `CliConfigError` (exit 2), `CliAuthError` (exit 3), `CliApiError` (exit 4), `CliInputError` (exit 5)
- [x] `client.py`: `ApiClient` con Bearer auth + mapping del envelope de error del API → `CliError` humano + hints accionables
- [x] `output.py`: paleta Webcafeína con `typer.echo` (mensajes) + Rich Tables (output denso). Modo `--json` global con `WCM_JSON=1`
- [x] **11 grupos de comandos**: setup, doctor, auth (login/logout/me), leads (list/get/refingerprint), projects (list/get/status/new/start/resume/cancel/export-checklist), campaigns (launch), residual-tasks (list/done), deploy. Plus shortcuts `wcm login` y `wcm logout`
- [x] **17 tests** con `CliRunner` + `respx`: help, login flow (cookie → token cache), logout limpia cache, leads list (Rich table), refingerprint, projects new/start/get-404-friendly-error, campaigns launch, API connect error con hint
- [x] Dos fixes durante desarrollo:
  - Rich Console cachea `sys.stdout` al construir → reconstruir por llamada con `file=sys.stdout`
  - Estado contaminado entre tests → `_isolate_state` autouse limpia `WCM_TOKEN`, `WCM_JSON`, paths
- [x] ADR-021 (doble entrypoint + CliError=ClickException)
- [x] Total repo: **227 passed + 2 skipped (Postgres)** con `.env` cargado

## Tareas completadas en sesión anterior (Fase 6)

- [x] Paquete `apps/worker/` con Celery 5.4 + SQLAlchemy sync (Celery es sync)
- [x] `celery_app.py` compartido conceptualmente con la API; el worker registra las tasks via `include=[...]` + import explícito en `__init__.py`
- [x] `db.py` con `session_scope()` context manager sync (commit/rollback automático)
- [x] `errors.py` con 20+ errores tipados (uno por subagente + Orchestration*)
- [x] `agents/base.py` con `BaseAgent` ABC + `AgentContext` + `AgentResult`
- [x] **8 subagentes REAL** (envuelven paquetes ya construidos):
  - `FingerprinterAgent` con `wcm_scraper_core.fingerprint` + persistencia en Lead
  - `EnricherAgent` con regex emails (anti-placeholder) + teléfonos ES + socials + scoring
  - `ScraperOriginAgent` BFS interno (httpx + BeautifulSoup), filtra a misma-host
  - `ContentExtractorAgent` aplica los extractors Wix/Hostinger/Webflow según builder_source
  - `SeoPreserverAgent` extrae title/meta/OG/canonical/hreflang/JSON-LD/h1 con avisos
  - `MultilangHandlerAgent` detección por `<html lang>` + count por idioma
  - `BricksTranspilerAgent` usa `transpile_page` + `validate_bricks_page`, persiste BricksPage
  - `WpDeployerAgent` usa REST upsert + WP-CLI bricks_import_content (async dentro de task sync)
- [x] **11 subagentes STUB** con `AgentNotImplementedError` + mensaje referenciando fase de implementación real
- [x] `pipeline.py` con `Orchestrator` state machine: 15 fases en orden canónico con `required` + `condition_attr` para skip lógico
- [x] **4 Celery tasks** registradas con `name=` matcheando los `send_task` del API:
  - `wcm.orchestrator.run_project` → ejecuta Orchestrator
  - `wcm.fingerprinter.run` → FingerprinterAgent (max_retries=2)
  - `wcm.prospector.run_campaign` → stub Fase 9
  - `wcm.clickup.sync_residuals` → stub Fase 10
- [x] Tests: 28 unit (celery_app registration, pipeline state machine con stubs en `_PhaseSpec` parametrizables, agentes REAL con mocks de httpx, agentes STUB validan mensaje)
- [x] Fix menor: `log.warning("...", extra={"msg": ...})` colisiona con `LogRecord.msg` reservado → renombrado a `reason`
- [x] ADR-020: distinción descriptors `.claude/agents/*.md` (Claude Code build-time) vs runtime `apps/worker/agents/*.py` (Python en producción)
- [x] Total repo a 2026-05-13: **210 passed + 2 skipped (Postgres)**

## Tareas completadas en sesión anterior (Fase 5)

- [x] Paquete `apps/api/` con FastAPI + uvicorn + pydantic-settings
- [x] `config.py` con `ApiSettings` leyendo `.env` + `CORS_ORIGINS` parseado desde CSV (pydantic-settings no parsea list[str] desde env por defecto)
- [x] `db/session.py` con async engine + `AsyncSession` factory + `get_session()` dependency
- [x] `errors.py` con `ApiError` + envelope JSON `{"error": {"code", "message", "details"}}` + mapping automático para errores de paquetes (WpClient*, Bricks*)
- [x] `security.py` con argon2 + JWT + cookie http-only + dependencies `get_current_user_payload` + `require_role(*roles)` + tokens separados para session vs opt-out RGPD
- [x] `tasks/celery_app.py` con app Celery compartida (broker Redis) + `tasks/enqueue.py` con send_task helpers
- [x] 10 routers montados:
  - `/health` + `/ready` (sin auth)
  - `/opt-out` (público RGPD, HTML con paleta Webcafeína, sin prefijo /api/v1)
  - `/api/v1/auth/{login,logout,me}`
  - `/api/v1/users` CRUD admin only
  - `/api/v1/leads` con filtros + refingerprint
  - `/api/v1/campaigns/launch`
  - `/api/v1/projects` + start/resume/cancel/phases
  - `/api/v1/residual-tasks` con sync ClickUp
  - `/api/v1/errors` lectura del error_log
  - `/api/v1/webhooks/clickup` con validación HMAC SHA-256
- [x] Total 32 rutas registradas + `/docs` Swagger UI
- [x] 33 tests unit con dependency override de `get_session` + `httpx.AsyncClient(ASGITransport)` (sin red, sin DB real)
- [x] Tests por categoría: health (2), security (6), auth router (7), authorization RBAC (5), opt-out RGPD (4), webhooks HMAC (3), projects+campaigns (6)
- [x] `pytest.ini` en raíz con `asyncio_mode = auto` para que tests asíncronos funcionen al ejecutar desde monorepo root
- [x] ADR-019 (versionado `/api/v1/` + endpoint RGPD fuera del prefijo)
- [x] Total repo: **182 passed + 2 skipped** (con `.env` cargado)

## Tareas completadas en sesión anterior (Fase 4)

- [x] Verificación end-to-end del sandbox Local by Flywheel: SSH, WP-CLI, REST API, Application Password
- [x] Workarounds documentados (ADR-018): `wp-cli.phar` descargado, PHP binario absoluto, socket MySQL volátil, user `test`
- [x] `.env` local creado con quoting correcto para paths con espacios; verificado source-able por bash + python-dotenv
- [x] SSH a localhost autorizado (`authorized_keys` con `id_ed25519.pub`)
- [x] Paquete `packages/wp-client/` con módulos: `config`, `errors`, `retries`, `rest`, `ssh_cli`
- [x] `WpClientConfig` con `from_env()` + `local_php_bin` + `local_mysql_socket` opcionales
- [x] Jerarquía de errores tipados (9 clases: WpClientError raíz + 8 subclases por causa)
- [x] `WpRestClient` async con basic auth + retries con backoff + verify SSL configurable + upsert idempotente por slug + bulk con BulkResult + bricks_import_page + import_redirects + upload_media + upsert_yoast_meta
- [x] `WpCliSshClient` con paramiko + invocación PHP-absoluto + override socket MySQL + helpers high-level (core, plugin, theme, search-replace, bricks_import_content, post_create, option_get/update)
- [x] 21 tests unit con respx para httpx + mocks paramiko
- [x] 8 tests integración contra sandbox WP 6.9.4 real (REST GET users/me, list/create/delete/upsert pages, CLI core version+is-installed+option get+search-replace dry-run)
- [x] ADR-018 (workarounds Local) + 2 issues nuevos (WCM-009 PHP, WCM-010 socket autodescubrir)
- [x] Fix menor: `postgres_engine` fixture envuelve también `create_engine` en try/except para skip limpio

## Tareas completadas en sesión anterior (Fase 3)

- [x] Investigación de proxies gratuitos viables (Webshare, ScraperAPI, listas públicas) → ADR-017
- [x] Paquete `packages/scraper-core/` con módulos: fetcher, browser, ua, rate_limit, cache, proxy, fingerprint, extractors, assets, sidecar
- [x] `ProxyRotator` layered: NoProxy → Webshare (free) → ScraperAPI (free) → Bright Data (paid)
- [x] `BrowserSession` async (Playwright) con stealth + locale ES + UA rotation, opcional `[browser]` extra
- [x] `UserAgentPool` con pool curado de 15 UAs reales + sticky por dominio + fallback a fake-useragent
- [x] `DomainRateLimiter` con jitter `[3-8]s` + cooldown 24h tras 3×{403,429,503}
- [x] `CacheBackend` Protocol + `InMemoryCache` (dev/tests)
- [x] Fingerprinter cascada 5 niveles con `patterns.yml` mantenible (10 tecnologías cubiertas)
- [x] Extractors Wix/Hostinger/Webflow con selectores documentados y mapeo a `BlockType`
- [x] Sidecar Node `webflow-sidecar.js` (Puppeteer-extra + stealth) para IX2; cliente Python `sidecar/__init__.py`
- [x] Asset discovery: imágenes (incl. srcset, picture, bg-image en CSS), fonts (@font-face, Google Fonts), vídeos (incluye iframe yt/vimeo)
- [x] 9 tests fingerprint + 17 extractors + 9 assets + 9 proxy + 8 rate_limit + 5 ua/cache = 57 passed
- [x] Fixtures HTML sintéticas representativas en `tests/fixtures/{wix,hostinger,webflow}/`
- [x] ADR-017 (proxy layered free→paid) supersede ADR-005
- [x] `.env.example` ampliado con `WEBSHARE_USER/PASSWORD`, `SCRAPERAPI_KEY`
- [x] `CLAUDE.md` §10 actualizado con la nueva estrategia anti-detección

## Tareas completadas en sesión anterior (Fase 2)

- [x] Investigación documentación pública Bricks Builder (academy.bricksbuilder.io, GitHub `wpgaurav/bricks-skills`, `sabiertas/bricks-mcp-server`, BricksSync) — fuentes consultadas listadas en SKILL.md
- [x] Esquema observacional v1 documentado en `.claude/skills/bricks-json-schema/SKILL.md` + `schema.json` (JSON Schema Draft 2020-12) + 3 examples
- [x] Paquete `packages/bricks-transpiler/` con módulos schema, ids, theme, validator, mappers, transpiler
- [x] Tipos Pydantic del esquema Bricks (`BricksElement`, `BricksThemeStyles`)
- [x] Generador determinista de IDs (`make_element_id` + `IdGenerator`) con blake2b/base36
- [x] 16 mappers ContentBlock → BricksElement(s) (hero, text, heading, image, gallery, cta, form, testimonial, pricing, faq, product-card, video, embed, divider, nav, footer, unknown)
- [x] Builder de Theme Styles con paleta Webcafeína por defecto
- [x] Validador `validate_bricks_page` con 8 tipos de error tipados
- [x] Transpiler orquestador que envuelve atómicos en section+container raíz
- [x] 39 tests nuevos (ids, validator, mappers, theme, e2e) — total 63 passed + 2 skipped
- [x] **Bug environmental descubierto**: macOS+Python 3.14 + flag UF_HIDDEN en .pth files. Workaround `scripts/fix-venv-hidden-pth.sh` + ADR-016 + WCM-008
- [x] 3 ADRs nuevos: ADR-014 (esquema observacional), ADR-015 (IDs deterministas), ADR-016 (workaround .pth)
- [x] 1 issue nuevo: WCM-008

## Tareas completadas en sesiones anteriores (Fase 1)

- [x] Commit aparte de la regla #11 añadida por el humano a CLAUDE.md (commit `4a73362`)
- [x] Paquete `packages/db-schema/` con `pyproject.toml`, `Base` + `TimestampMixin` + naming convention estable
- [x] 16 modelos SQLAlchemy 2.x + `OptOutLog` (17 tablas totales)
  - `users`, `leads`, `lead_enrichments`, `opt_out_log`, `outreach_sequences`, `outreach_sends`,
    `projects`, `project_phases`, `scraped_pages`, `assets`, `content_blocks`, `bricks_pages`,
    `woo_products`, `seo_redirects`, `residual_tasks`, `audit_log`, `error_log`
- [x] Alembic configurado (`alembic.ini`, `env.py`, `script.py.mako`)
- [x] Migración inicial `0001_initial_schema.py` manual con:
  - `CREATE EXTENSION vector`
  - Todas las tablas con sus PKs, FKs, índices y unique constraints
  - Vector index `ivfflat` con `vector_cosine_ops` en `leads.embedding (1024 dim)`
  - Downgrade reversible completo
- [x] Paquete `packages/shared-types/` con enums canónicos en `wcm_types/enums.py`
- [x] Pydantic v2 schemas (Create/Update/Read) por entidad en `wcm_types/schemas/*.py`
- [x] `wcm_db.enums` re-exporta desde `wcm_types.enums` (fuente única)
- [x] Script `scripts/gen-ts.sh` + comando raíz `pnpm gen:types`
- [x] Generación real de `ts/index.d.ts` con `pydantic2ts` + `json-schema-to-typescript`
- [x] Tests: 17 passed + 2 skipped (Postgres) con SQLite no-touch
- [x] Validado: `alembic upgrade head --sql` produce SQL Postgres válido offline
- [x] 3 ADRs nuevos: ADR-010 (embedding voyage 1024d), ADR-011 (enums en shared-types), ADR-012 (pydantic2ts)
- [x] 1 issue nuevo: WCM-007 (deduplicar alias enums en TS generado)
- [x] `.env.example` ampliado con sección Embeddings (`VOYAGE_API_KEY`, `VOYAGE_EMBEDDING_MODEL`)

---

## Próximas tareas inmediatas (Fase 13 — Tests e2e)

Cuando el humano apruebe Fase 12, ejecutar en orden:

1. **PREREQ humano**:
   - Acceso a un sandbox real (Wix demo + WP destino) para test golden path completo.
   - Decisión sobre coverage threshold (¿70% packages, 50% apps?).
2. **Playwright Test** en dashboard: e2e de login → list → detail → start project. Headless en CI.
3. **e2e Python**: `tests/e2e/test_full_migration.py` — fixture que crea un Project en BD + ejecuta orchestrator con HTML de Wix fixture + valida que se persiste BricksPage + assets + checklist. Sin red real (mocks de WP/R2).
4. **Coverage**: añadir `pytest-cov`, configurar threshold en `pytest.ini` y reporte HTML.
5. **CI matrix**: Python 3.13 + 3.14, Node 20 + 22 para detectar regresiones de versión.
6. **Visual regression**: snapshot de las páginas críticas del dashboard con Playwright (header, leads table, project detail).
7. Commit: `feat(e2e): full migration test + playwright dashboard`.

---

## Bloqueos / decisiones humanas pendientes

| ID | Descripción | Necesario para fase | Dueño |
|---|---|---|---|
| WCM-001 | Export JSON real de Bricks Builder mínimo | 2 | humano |
| ~~WCM-002~~ | ~~Datos legales Webcafeína~~ | ✅ cerrado en Fase 9 (CIF B10463990, Cáceres) | — |
| WCM-003 | URLs reales para calibrar skills extracción Wix/Hostinger/Webflow | 3 | humano |
| WCM-005 | Confirmar lista ClickUp por defecto para tareas residuales | 10 | humano |
| WCM-007 | Deduplicar alias enums en `ts/index.d.ts` | post-Fase 1 | técnico (no bloquea) |

(detalle en [`ISSUES.md`](./ISSUES.md))

---

## Decisiones tomadas esta sesión (Fase 12)

- **systemd nativo** (ADR-030): regla #1 prohíbe Docker. systemd + journald es estándar en cualquier Linux y elimina runtime adicional. Cada unit con hardening explícito (NoNewPrivileges, ProtectSystem=strict, etc.).
- **Single-server WHM** en MVP (ADR-031): reutiliza infra cPanel existente, ~50€/mes vs ~250€/mes en multi-nodo cloud. Cabe holgado para <100 migraciones/mes. Migración a multi-nodo cuando el volumen lo exija.
- **Templates con `envsubst`**: los .service y .conf de Nginx tienen `${WCM_APP_DIR}`, `${WCM_USER}`, `${WCM_PORT_*}`. Un script de install renderiza con `envsubst` antes de copiar a `/etc/systemd/system/` o `/etc/nginx/conf.d/`. Permite mismas plantillas en dev/staging/prod.
- **`/metrics` y `/health/deep` con ACL Nginx**: aunque la API permitiría exponerlos públicamente (sin auth), bloqueamos a `127.0.0.1` + IPs internas explícitas. Evita exponer la topología y métricas de uso al mundo.
- **GitHub Actions con `on: pull_request + push:main` pero sin remote aún**: workflows escritos y validados (`yaml.safe_load`), pero ADR-013 difiere el push del repo a Fase 15. Cuando llegue, el CI ya está listo sin tocar.
- **`deploy.sh` guarda SHA previo antes de cualquier cambio**: rollback es `deploy.sh <prev_sha>`. Idempotente.
- **NUNCA escalar `wcm-beat` a >1**: duplicaría todas las tareas programadas (retention_sweep dos veces, etc.). Documentado en ADR-030 y en el runbook.
- **`task_acks_late=true`** ya configurado en Celery (Fase 6): combinado con idempotencia en cada task, sobrevive a kill mid-task durante restarts del worker.

## Decisiones tomadas sesión anterior (Fase 11)

- **Observabilidad 100% perezosa**: ADR-028. Sin DSN, sin token, no se inicializa nada. Permite levantar la app en dev/CI sin cuentas externas.
- **PII off por defecto** en Sentry (api/worker/dashboard): `send_default_pii=False`. No queremos que emails de leads o credenciales aparezcan en Sentry.
- **Sin colores en logs** incluso en dev: stdout va a journald/archivos sin escape codes. ConsoleRenderer con `colors=False` mantiene legibilidad pero no rompe pipes.
- **Registry Prometheus propio** (no global default): evita contaminación entre tests y deja los metrics dump limpios (sin `python_gc_objects_collected` y friends).
- **Cardinalidad controlada en métricas HTTP**: el `path` se toma del route template (`/projects/{id}`) en lugar del path crudo, para no explotar Prometheus con un counter por cada ID.
- **Worker sin `/metrics` HTTP en Fase 11**: el worker no es un servidor HTTP. En Fase 12 lo expondrá vía sidecar simple o `start_http_server(9000)`.
- **Sentry SDK Next.js v9**: la última stable (sept 2025). Compatible con Next.js 15 + React 19.
- **Dashboard Sentry con DSN público (`NEXT_PUBLIC_*`)** en cliente: es lo esperado por Sentry; el panel filtra por origin/whitelist.

## Decisiones tomadas sesión anterior (Fase 10)

- **Resend único proveedor email** (ADR-025). Free tier 3k/mes cubre MVP. Webhook nativo con HMAC ya soportado.
- **R2 vía boto3** (ADR-026): S3-compat aísla el código de la decisión de proveedor; migrar a S3/B2 cuesta cambiar `endpoint_url`.
- **Sync ClickUp con `clickup_task_id`** (ADR-027): columna ya existía en schema; añadimos tag `wcm-residual-<id>` para join inverso desde ClickUp.
- **Separación OutreachComposer vs OutreachSender**: el composer genera drafts (Fase 9), el sender los envía (Fase 10). Dos agents distintos, dos errores tipados distintos. Aporta claridad y test isolation.
- **Doble check anti-spam en send**: aunque el composer ya verifica opt_out_log al crear el draft, el sender vuelve a verificar justo antes de enviar — pueden pasar días entre composer y sender, y un opt-out intermedio debe respetarse.
- **Status promotion "no retrocede"** en webhook Resend: una vez OPENED, no degradamos a SENT aunque llegue otro evento `email.sent` tardío. Implementado con `_STATUS_PRIORITY` y `_highest_status`.
- **AssetOptimizer defensivo**: si R2 no está configurado, el asset queda en `OPTIMIZED` (no `FAILED`) y un re-run lo termina cuando aparezca la config. Errores de descarga no rompen el batch — solo marcan ese asset como pendiente.
- **Sin cwebp binario**: Pillow encoda WebP nativo si está compilado con libwebp (lo está en wheels precompiladas). Evita dep nativa adicional.
- **Celery beat embebido en el mismo proceso**: en producción WHM, una unidad systemd separada (`wcm-beat.service`) levantará `celery beat`. La configuración del schedule vive en `celery_app.py` (un solo lugar).

## Decisiones tomadas sesión anterior (Fase 9)

- **sentence-transformers + multilingual-e5-large** sustituye Voyage AI (ADR-023, supersede ADR-010). Razones: 100% gratuito perpetuo, 1024 dim match exacto con el schema, mejor cobertura ES que BGE-M3, sin dep externa que pueda romper. Trade-off aceptado: ~50ms/embedding en CPU vs ~30ms con Voyage. En MVP es irrelevante; con miles de leads/min consideraremos GPU.
- **Google Places API legacy** en vez de New (ADR-024). La API key del proyecto solo tiene la legacy habilitada; cambiar a New requeriría rehabilitar billing y migrar. El cliente está aislado en un módulo (`directories/google_places.py`) — si en el futuro se migra a New, solo cambia ese fichero.
- **Embedding nunca bloquea el enrichment**: si sentence-transformers falla o el modelo tiene dim incorrecta, el lead se enriquece igual con emails/teléfonos/socials y `embedding.computed=False` queda registrado en el audit_log.
- **Cache key sin api_key**: el cache de Google Places excluye explícitamente `key=` de la cache key para evitar filtraciones si el cache se serializa.
- **Validación legal estricta**: el OutreachComposerAgent rechaza cualquier body que no contenga razón social, CIF, dirección y URL opt-out. Versión `v1.0` persistida en cada secuencia para trazabilidad.
- **Worker no comparte JWT_SECRET con la API**: la API emite el opt-out token al encolar; el worker solo renderiza la URL. Reduce superficie de exposición del secret.

## Decisiones tomadas sesión anterior (Fase 8)

- **JetBrains Mono en toda la UI** (ADR-022) por preferencia del operador. Look denso terminal-friendly coherente con la herramienta interna.
- **Server Components por defecto** + Client Components solo para interactividad (forms, action buttons).
- **Cookie http-only `wcm_session`** propagada con `credentials: "include"` + rewrite `/api/v1/*` → API para evitar CORS en dev y unificar dominio en prod.
- **Build `output: "standalone"`** para que systemd arranque con `node server.js` sin necesitar `next` en el servidor (Fase 12).
- **Logo SVG**: pendiente. Mientras: wordmark de texto "WEBCAFEÍNA" en lima + icono `Activity` de lucide.

## Decisiones tomadas sesión anterior (Fase 7)

- **Doble entrypoint** `webcafeina-migrator` + `wcm` (ADR-021).
- **`CliError` hereda de `click.ClickException`** para captura automática por Typer + tests con `CliRunner`.
- **`output.error` a stdout** en modo humano (no stderr), salvo modo `--json` donde debe ir a stderr para mantener stdout limpio.
- **Rich solo para tablas**, `typer.echo` para mensajes simples (Rich tiene buffering interno que pelea con `CliRunner`).
- **Cobertura completa con stubs accionables**: comandos como `export-checklist` y `deploy` muestran un mensaje claro indicando en qué fase se materializan.

## Decisiones tomadas sesión anterior (Fase 6)

- **Subagentes runtime separados de descriptors** (ADR-020): `.claude/agents/*.md` son build-time (Claude Code), `apps/worker/agents/*.py` son runtime (clases Python con `BaseAgent`).
- **Alcance MVP con stubs `NotImplementedError`**: 8 subagentes REAL (cuyos paquetes ya existen) + 11 STUB con mensaje accionable. `AgentNotImplementedError` se trata como skip en el orchestrator.
- **Worker sync (SQLAlchemy sync)** mientras la API es async. Comparten BD, schema y enums; cambian el driver (`asyncpg` vs `psycopg`).
- **`CELERY_TASK_ALWAYS_EAGER=true`** en tests para que `.apply()` funcione sin broker Redis.

## Decisiones tomadas sesión anterior (Fase 5)

- **Versionado `/api/v1/...`** + endpoint público RGPD fuera del prefijo (ADR-019).
- **Auth dual**: cookie http-only `wcm_session` para dashboard + `Authorization: Bearer` / `x-wcm-token` para CLI; ambos llevan el mismo JWT.
- **Roles**: admin (todo) / operator (read+write excepto users) / viewer (solo lectura).
- **Tests sin DB real**: dependency override de `get_session` con `AsyncMock`. Aprobado en pregunta inicial de fase.
- **CORS desde CSV en `.env`**: pydantic-settings no parsea `list[str]` desde env por defecto. La var es `cors_origins_raw: str` y se expone como `cors_origins` property.

## Decisiones tomadas sesión anterior (Fase 4)

- **Workarounds Local by Flywheel** (ADR-018): `WpClientConfig` añade `local_php_bin` + `local_mysql_socket` opcionales; `WpCliSshClient` invoca PHP-absoluto + override socket cuando están definidos. Producción WHM/cPanel los deja `None` y usa `wp` binario global con DB normal.
- **Sandbox dev validado contra Local**: user admin = `test` (no `admin`), HTTPS con cert auto-firmado (`WP_VERIFY_SSL=false` en dev), `wp-cli.phar` descargado al directorio del site.
- **`.env` con quoting estricto** para paths con espacios (necesario para `source .env` bash + python-dotenv sin sorpresas).

## Decisiones tomadas sesión anterior (Fase 3)

- **Proxy layered free→paid** (ADR-017, supersede ADR-005): NoProxy → Webshare → ScraperAPI → Bright Data, todos opcionales por env vars. Coste real €0 hasta volumen alto.

## Decisiones tomadas sesión anterior (Fase 2)

- **Esquema Bricks observacional v1** desde docs públicas (ADR-014). Provisional hasta WCM-001.
- **IDs deterministas** blake2b/base36 6 chars (ADR-015) para idempotencia.
- **Workaround macOS+Python 3.14** para .pth con flag hidden (ADR-016): `scripts/fix-venv-hidden-pth.sh`.

## Decisiones tomadas sesión anterior (Fase 1)

- **Embeddings**: `voyage-multilingual-2` con **1024 dim** (ADR-010).
- **Enums canónicos** en `wcm_types`, `wcm_db.enums` re-exporta (ADR-011).
- **Tipos TS auto**-generados con `pydantic2ts` + `json-schema-to-typescript` (ADR-012).
- **No SQLite en tests**: los tipos PG-específicos (Vector, ARRAY, JSONB, UUID) no se simulan en tests; los tests Postgres se marcan con `@pytest.mark.postgres` y se skippean sin BD.
- **Commit en `main`**: como en Fase 0, sin feature branch (revisión humana entre fases es suficiente).
- **Repo GitHub diferido al final de Fase 15** (ADR-013, supersede ADR-008). Trabajo local hasta entonces. Fase 12 escribe los workflows pero no se ejecutan hasta el push final.

---

## Notas para la próxima sesión

- Antes de tocar nada, leer este fichero y `CLAUDE.md`.
- **NO leer `docs/humanos/`** (regla #11 — zona humana).
- Tras CUALQUIER `pip install` en el venv, ejecutar `bash scripts/fix-venv-hidden-pth.sh` (ADR-016).
- Test suite total a 2026-05-13 (tras Fase 12): **379 passed + 10 skipped** (Postgres real sin BD) + 15 TS. Para correr: `set -a; source .env; set +a; pytest -q` desde la raíz.
- Sandbox Local WP corriendo en `https://migrator-sandbox.local`; usuario admin = `test`; PHP `8.2.29+0` + socket en `run/H1F_xStai/...` (vigilar si Local cambia IDs).
- Issues abiertos prioritarios:
  - WCM-001 (P0) export real Bricks — sigue pendiente; sería el momento ideal con sandbox listo.
  - WCM-002 (P1) datos legales Webcafeína.
  - WCM-003 (P1) URLs reales por builder para calibrar scraper.
  - WCM-008..010 (P2-P3) workarounds entorno; no bloquean.
- Validar Fase 1 corriendo `alembic upgrade head` contra Postgres+pgvector sigue pendiente.
