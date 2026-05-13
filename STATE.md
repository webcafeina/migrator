# STATE.md — Cursor de avance Webcafeína Migrator

> Este fichero se actualiza al final de cada sesión de construcción.
> Lo lee Claude al iniciar cada nueva sesión para retomar exactamente donde quedó.

---

## Fase actual

- **Fase 0 — Bootstrap**: ✅ Completada (commit `f7aa1a7`)
- **Fase 1 — DB y modelos**: ✅ Completada (commit `3ad2b7b`)
- **Fase 2 — Bricks transpiler**: ✅ Completada (commit `d653557`)
- **Fase 3 — Scraper core**: ✅ Completada esta sesión
- **Próxima fase**: Fase 4 — WP client

> 🟡 **Antes de iniciar Fase 4**, el humano debe (a) revisar Fase 3, (b) preparar credenciales de un WordPress sandbox accesible vía SSH + WP-CLI (host, user, password/key, app password REST). (c) WCM-001 sigue abierto y será necesario para smoke contra Bricks real en Fase 4.

---

## Tabla de progreso

| Fase | Nombre | Estado | Notas |
|---|---|---|---|
| 0 | Bootstrap | ✅ Completada | Estructura + agentes + skills + memoria |
| 1 | DB y modelos | ✅ Completada | 17 tablas, migración 0001, pydantic schemas, tipos TS auto |
| 2 | Bricks transpiler | ✅ Completada | Esquema observacional v1, 16 mappers, validador, theme styles, 63 tests |
| 3 | Scraper core | ✅ Completada | Playwright wrapper + 3 extractors + proxy layered free→paid (ADR-017) + sidecar Puppeteer + 57 tests |
| 4 | WP client | ⏳ Pendiente | Bloqueada por credenciales WP sandbox |
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

## Tareas completadas en la última sesión (Fase 3)

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

## Próximas tareas inmediatas (Fase 4 — WP client)

Cuando el humano apruebe Fase 3, ejecutar en orden:

1. **PREREQ humano**: WordPress sandbox accesible. Se necesita:
   - Host + SSH key path (paramiko)
   - WP-CLI instalado en el sandbox (`which wp` debe devolver path)
   - Usuario REST API con Application Password (rol admin para Bricks import)
2. Implementar `packages/wp-client/`:
   - `WpRestClient` (skill `wp-rest-bulk`): bulk insert pages/posts, media upload, Yoast meta, Redirection, Gravity Forms, WPML
   - `WpCliSshClient` (skill `wpcli-ssh`): `wp core install`, `wp plugin install`, `wp post update --post_meta=_bricks_page_content_2`
   - Idempotencia por slug/SKU/source_path; retries con backoff exponencial
3. Tests contra mocks de respuestas REST. Tests integración opt-in contra sandbox real si se proporciona.
4. WCM-001 (export real Bricks): si el humano lo aporta antes, ajustar bricks-transpiler en paralelo.
5. Commit: `feat(wp): client with REST and CLI`.

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

## Decisiones tomadas esta sesión (Fase 3)

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
- Tras CUALQUIER `pip install` en el venv, ejecutar `bash scripts/fix-venv-hidden-pth.sh` (ADR-016). El último install marcó hidden los .pth otra vez — el script lo corrige.
- Para Fase 4 necesitas: WordPress sandbox con SSH + WP-CLI + Application Password REST.
- Test suite total a 2026-05-13: **120 passed + 2 skipped** (db-schema 17, shared-types 12, bricks-transpiler 63 pero comparten fixtures con db-schema → en agregado 63 únicos, scraper-core 57). Para correr todos: `python -m pytest packages -q` desde la raíz.
- Calibración Fase 3 con URLs reales: cuando me pases URLs reales por builder (WCM-003), comparar fingerprint output + extractor blocks vs lo capturado y ajustar selectores.
- Validar Fase 2 contra Bricks real (WCM-001) sigue pendiente.
- Tests Postgres siguen skippeados hasta que ejecutes `alembic upgrade head` contra Postgres+pgvector real (Fase 1).
