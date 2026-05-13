# STATE.md — Cursor de avance Webcafeína Migrator

> Este fichero se actualiza al final de cada sesión de construcción.
> Lo lee Claude al iniciar cada nueva sesión para retomar exactamente donde quedó.

---

## Fase actual

- **Fase 0 — Bootstrap**: ✅ Completada (commit `f7aa1a7`)
- **Fase 1 — DB y modelos**: ✅ Completada (commit `3ad2b7b`)
- **Fase 2 — Bricks transpiler**: ✅ Completada (commit `d653557`)
- **Fase 3 — Scraper core**: ✅ Completada (commit `01c93d4`)
- **Fase 4 — WP client**: ✅ Completada esta sesión, **validada contra sandbox real Local by Flywheel**
- **Próxima fase**: Fase 5 — API backend

> 🟢 **Para iniciar Fase 5** no se necesita ningún prereq humano nuevo. WCM-001 sigue abierto pero NO es bloqueante para Fase 5 (la integración wp_deployer + bricks-transpiler la haremos en Fase 6 worker).

---

## Tabla de progreso

| Fase | Nombre | Estado | Notas |
|---|---|---|---|
| 0 | Bootstrap | ✅ Completada | Estructura + agentes + skills + memoria |
| 1 | DB y modelos | ✅ Completada | 17 tablas, migración 0001, pydantic schemas, tipos TS auto |
| 2 | Bricks transpiler | ✅ Completada | Esquema observacional v1, 16 mappers, validador, theme styles, 63 tests |
| 3 | Scraper core | ✅ Completada | Playwright wrapper + 3 extractors + proxy layered free→paid (ADR-017) + sidecar Puppeteer + 57 tests |
| 4 | WP client | ✅ Completada | REST + WP-CLI vía paramiko + workarounds Local (ADR-018) + 29 tests (21 unit + 8 integración contra sandbox real WP 6.9.4) |
| 5 | API backend | ⏳ Pendiente | |
| 6 | Worker + subagentes | ⏳ Pendiente | |
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

## Tareas completadas en la última sesión (Fase 4)

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

## Próximas tareas inmediatas (Fase 5 — API backend)

Cuando el humano apruebe Fase 4, ejecutar en orden:

1. Implementar `apps/api/` (FastAPI + uvicorn):
   - Routers REST por dominio: `/leads`, `/projects`, `/projects/{id}/phases`, `/campaigns`, `/errors`, `/users`, `/auth`, `/webhooks/clickup`, `/opt-out` (RGPD)
   - Auth JWT con cookies de sesión; Application Password style para CLI clients
   - SQLAlchemy async session dependency injection
   - Pydantic schemas ya construidos en `wcm_types` se reutilizan tal cual
   - Endpoint `/health` y `/ready` para sondas
2. Tests con `httpx.AsyncClient(app=app)` directo (sin levantar servidor).
3. OpenAPI auto-generado en `/docs` y `/openapi.json`.
4. Integración con Celery (`apps/worker`) — placeholders de `enqueue_*` que en Fase 6 se materializan.
5. Errores: handler global que mapea `WpClientError`, `BricksTranspileError`, etc. a HTTP 4xx/5xx tipados.
6. Commit: `feat(api): backend with celery integration`.

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

## Decisiones tomadas esta sesión (Fase 4)

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
