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
- **Fase 6 — Worker + subagentes operativos**: ✅ Completada esta sesión
- **Próxima fase**: Fase 7 — CLI

> 🟢 **Para iniciar Fase 7** no se necesita ningún prereq humano nuevo. CLI con Typer envuelve los endpoints del API + algunos shortcuts directos al worker.

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
| 7 | CLI | ⏳ Pendiente | |
| 8 | Dashboard | ⏳ Pendiente | |
| 9 | Prospección | ⏳ Pendiente | Bloqueada por WCM-002 + Voyage API key |
| 10 | Integraciones externas | ⏳ Pendiente | |
| 11 | Observabilidad | ⏳ Pendiente | |
| 12 | Infra/Deploy | ⏳ Pendiente | |
| 13 | Tests e2e | ⏳ Pendiente | |
| 14 | Documentación | ⏳ Pendiente | |
| 15 | Hardening | ⏳ Pendiente | |

---

## Tareas completadas en la última sesión (Fase 6)

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

## Próximas tareas inmediatas (Fase 7 — CLI)

Cuando el humano apruebe Fase 6, ejecutar en orden:

1. Implementar `cli/` con Typer + Rich:
   - `wcm setup` — onboarding interactivo del operador
   - `wcm prospect --sector X --region Y` (encola campaña vía API)
   - `wcm leads list/get/score` (consulta API)
   - `wcm new --source URL --client NAME` → crea proyecto vía API
   - `wcm project status/resume/cancel ID`
   - `wcm project export-checklist ID` → descarga checklist
   - `wcm deploy --env prod` → trigger deploy scripts (Fase 12 lo amplía)
   - `wcm doctor` → comprueba .env, conectividad API/DB/Redis, status del worker
2. Cliente HTTP interno (httpx) con manejo de Auth Bearer + descubrimiento de URL desde `.env`.
3. Output con Rich: tablas densas para listas, progress bars, spinners.
4. Modo `--json` para integración con scripts.
5. Tests con `CliRunner` de Typer.
6. Commit: `feat(cli): operator commands`.

---

## Bloqueos / decisiones humanas pendientes

| ID | Descripción | Necesario para fase | Dueño |
|---|---|---|---|
| WCM-001 | Export JSON real de Bricks Builder mínimo | 2 | humano |
| WCM-002 | Datos legales Webcafeína (CIF, dirección, URL privacidad) | 9 | humano |
| WCM-003 | URLs reales para calibrar skills extracción Wix/Hostinger/Webflow | 3 | humano |
| WCM-005 | Confirmar lista ClickUp por defecto para tareas residuales | 10 | humano |
| WCM-007 | Deduplicar alias enums en `ts/index.d.ts` | post-Fase 1 | técnico (no bloquea) |

(detalle en [`ISSUES.md`](./ISSUES.md))

---

## Decisiones tomadas esta sesión (Fase 6)

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
- Test suite total a 2026-05-13 (tras Fase 4): **149 passed + 2 skipped** (Postgres real sin BD). Para correr: `set -a; source .env; set +a; pytest packages -q` desde la raíz.
- Sandbox Local WP corriendo en `https://migrator-sandbox.local`; usuario admin = `test`; PHP `8.2.29+0` + socket en `run/H1F_xStai/...` (vigilar si Local cambia IDs).
- Issues abiertos prioritarios:
  - WCM-001 (P0) export real Bricks — sigue pendiente; sería el momento ideal con sandbox listo.
  - WCM-002 (P1) datos legales Webcafeína.
  - WCM-003 (P1) URLs reales por builder para calibrar scraper.
  - WCM-008..010 (P2-P3) workarounds entorno; no bloquean.
- Validar Fase 1 corriendo `alembic upgrade head` contra Postgres+pgvector sigue pendiente.
