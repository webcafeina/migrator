# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Versionado [SemVer](https://semver.org/lang/es/).

---

## [Unreleased]

Cambios todavía sin tag.

---

## [0.22.0] — 2026-05-21

Sprint **Fidelidad visual al origen** — arquitectura híbrida heurística + Claude Vision + RAW_HTML para empezar a aproximar la migración a la web origen. Tras el run sobre mariya.design (50 páginas) el destino aún no se parece visualmente al origen, pero la base está montada para v0.23.0 (element-level styling).

### Added

- **W — R2 prefix unificado**: todos los agentes convergen en `wcm/projects/{id}/`. Limpia objetos huérfanos de proyectos 13-22 con prefix antiguo `projects/{id}/`.
- **G.1 — Texto completo por sección**: `_classify_section` devuelve `list[ExtractedBlock]` y `_extract_text_blocks` recorre todos los h1-h6/p/ul/ol (1745 vs 424 bloques en mariya.design, +311%).
- **G.6 — Paleta Bricks con shape `{id, name, raw}`** + DEFAULT_PALETTE actualizada + mappers referencian `var(--bricks-color-X)` consistentemente.
- **G.7 — Google Fonts loader** vía `custom_code.headerScripts` con `<link rel=preconnect>` + CSS2 URL con ital + 400-700. `_WIX_TO_GOOGLE_FONT` mapea aliases internos Wix (`orig_albra_sans_*`) a fonts disponibles.
- **AI.1 — Captura full-page screenshot + section bboxes**. `_DETECT_SECTIONS_JS` devuelve [{idx, selector, bbox}] en coordenadas documento. Pillow recorta y sube a R2 con clave `wcm/projects/{pid}/sections/{page_idx}/{idx}.png`. Persistido en `scraped_pages.section_screenshots_json` (JSONB).
- **AI.2 — `ClaudeVisionClient`** async wrapper Anthropic SDK con `tool_use` forzado (`emit_bricks_elements`), retry interno con backoff exponencial + jitter, cache BD por hash(screenshot+html+selector). Pricing tracker (claude-sonnet-4-6: $3/$15 per Mtok). **`max_retries=0` del SDK** para evitar bucle de reintento sobre 429.
- **AI.3 — Migración Alembic 0014**: `scraped_pages.section_screenshots_json`, `content_blocks.{section_screenshot_url, coverage_score, ai_processed}`, tabla `ai_section_cache(input_hash, project_id ondelete=SET NULL, response_json, tokens_in/out, cost_usd)`.
- **AI.4 — `AiAssistAgent`** nueva fase entre `theme_styles` y `transpile_bricks`. Procesa bloques `UNKNOWN` o `coverage_score<0.6`. Concurrency=5, budget cap `WCM_AI_BUDGET_USD_PER_PROJECT` (default $10), cap absoluto bloques por proyecto `WCM_AI_MAX_BLOCKS_PER_PROJECT` (default 30, 0=sin cap). Errores tipados: `ClaudeVisionApiError`, `ClaudeVisionAuthError`, `ClaudeVisionInvalidOutputError`. Auth error → abort + resto a RAW.
- **RAW mappers — `map_ai_generated` + `map_raw_html`** con CSS namespace tinycss2. RAW envuelve HTML en `<div data-wcm-block="<hash6>">` + `<style>` namespaceado. Sanitización agresiva del HTML (sin `<script>`, `<?php`, handlers `on*=`). Fallback regex si tinycss2 falla.
- **`BlockType.AI_GENERATED` + `BlockType.RAW_HTML`** nuevos enums.
- **Pipeline `ai_assist`** insertado como `required=False` entre theme y transpile.
- **Stepper UI** con fase `ai_assist`.
- **`ANTHROPIC_API_KEY` + `WCM_AI_*` env vars** documentadas en `.env.example`.

### Changed

- **Extractor Wix** clasifica secciones devolviendo múltiples sub-bloques (h2 + p + ul) en vez de uno único genérico.
- **`BricksThemeStyles`** gana `post_types` (default `["page","post"]`) y `custom_code` (Google Fonts headerScripts). MERGE estrategia al persistir `bricks_global_settings` para no perder `postTypes` (bug "Edit with Bricks" en v0.21.x).
- **`BricksElement.parent` validator** regex `^[a-z0-9]{6}$` en vez de `.islower()` (que devolvía False sobre IDs todo-dígitos).
- **`bricks_transpiler` UPSERT** por `(project_id, slug, lang)`: restart conserva filas previas; INSERT puro chocaba con la unique constraint.

### Fixed

- **`_apply_raw_html`** ahora carga `scraped_pages.css_extracted` del page padre y lo guarda en `content_json.css`. Antes hardcodeaba `""` → 136 bloques RAW renderizaban sin estilos (defaults browser sans-serif). El mapper `map_raw_html` ya tenía la lógica tinycss2 de namespace; solo le faltaba CSS de entrada.
- **`visual_diff` loop infinito en draft pages**: pre-check `wp_post_status='publish'`, timeout per-call, cap consecutivo de fallos, respeto `WP_VERIFY_SSL`.
- **`optimize_assets` UniqueViolation** en hashes duplicados via `existing_ready` dedup.
- **Anthropic SDK bucle infinito 24 → 40 min**: combinación SDK retry default + nuestro `_call_with_retry` + concurrency=5 saturaba. Resuelto con `AsyncAnthropic(max_retries=0)` + cap absoluto bloques.
- **Canonical URL dedup** en BFS scraper (proyecto 14, `(project_id, slug, lang)=(14, home, en)` duplicado).
- **`pipeline-stepper.test.tsx`** actualizado a 17 fases canónicas (era 15 antes de añadir `ai_assist`).

### Limitaciones conocidas

- Heurística captura contenido pero NO computed styles → mappers atómicos emiten elementos sin color/font-size/padding del origen → look genérico Bricks default.
- `MAX_CSS_BYTES = 256*1024` en `playwright_fetcher.py` trunca CSS de Wix (~500KB real).
- AI Vision casi nunca corre por rate-limit del tier Anthropic del operador (8/145 procesados en mariya.design).
- RAW_HTML inflaba postmeta WP (137 × 262KB) → tumbó el servidor cPanel del destino.

Estas limitaciones son el motor del sprint v0.23.0 (element-level styling + globalClasses + RAW eliminado).

---

## [0.20.0] — 2026-05-19

Sprint v0.20.0+ — **18 ADRs (ADR-037 a ADR-054) + 34 tareas de
implementación** distribuidas en 8 bloques (migraciones → backend →
adapters → endpoints → UI → CLI → docs). Sprint de cierre técnico previo
al primer test E2E con cliente real: cubre publicación tras revisión,
snapshot/rollback por SQL, restart, force-rerun, threshold visual diff
configurable, importación de pedidos Wix/Webflow con PII cifrada + RGPD,
Playwright para SPAs, eliminación dura de proyectos con confirmación
literal, y badges UNKNOWN.

### Added

- **ADR-039** — Endpoint `POST /api/v1/projects/{id}/publish` + PublishAgent + Celery task. Pasa todas las páginas migradas de `draft` a `publish` en lote. CLI `wcm projects publish ID`. Botón "Publicar todo" en `ProjectActions` (solo si status=completed|qa_failed).
- **ADR-040** — `PlaywrightFetcher` helper async con browser+context reuse. Scraper origin usa Playwright por defecto para Wix y Webflow; httpx para el resto. Override global `SCRAPE_USE_PLAYWRIGHT=true|false`. Fallback automático a httpx si Playwright no está instalado. §10.1 nueva en `docs/despliegue.md` con instalación + verificación.
- **ADR-041** — Endpoint `POST /api/v1/projects/{id}/restart` para re-arrancar proyectos `rolled_back`. CLI `wcm projects restart ID`. Botón "Re-arrancar".
- **ADR-042** — `PreDeploySnapshotAgent` nueva fase pipeline antes de `wp_deployer`. `wp db export` por SSH; path en `projects.pre_deploy_snapshot_*`. RollbackAgent con branching: snapshot → `wp db import` (restauración completa); fallback REST DELETE MVP si snapshot inaccesible.
- **ADR-043** — Orchestrator soporta `force_rerun_all` en Resume. Default False = skip COMPLETED (Resume rápido); True = re-ejecuta TODO. Propagado a enqueue + endpoint `/resume?force_rerun_all=true` + CLI `--force-rerun-all/-f` + toggle UI.
- **ADR-044** — `projects.visual_diff_threshold` (FLOAT NULL CHECK 0..1). VisualDiffAgent genera ResidualTask VISUAL_CONTENT por página bajo umbral (cascada: project > env `VISUAL_DIFF_RESIDUAL_THRESHOLD` > 0.70). Panel "Configuración avanzada" con inputs editables + CLI `wcm projects set-visual-threshold ID 0.75`.
- **ADR-045** — Tabla `woo_orders` con PII cifrada Fernet (billing/shipping/email/name). Adapters Wix + Webflow extendidos con `list_orders()` y `list_coupons()`. WooMigratorAgent importa pedidos del adapter + ResidualTask cupones mejorada (conteo real + muestra de códigos). Celery beat `retention_sweep` purga `woo_orders` tras `WOO_ORDERS_RETENTION_DAYS` (default 30d) — cumplimiento RGPD.
- **ADR-047** — Endpoint combinado `POST /api/v1/projects/with-start` (crear + arrancar en una sola llamada).
- **ADR-049** — Orchestrator captura Exception genérica — fases `required=False` continúan tras fallo; las `required=True` siguen bloqueando.
- **ADR-050** — `projects.max_pages_scrape` (INT NULL CHECK 1..500). ScraperOriginAgent aplica cascada (project > env `SCRAPE_MAX_PAGES_DEFAULT=50` > 50) y genera ResidualTask POST_GO_LIVE si el cap se alcanza. UI Configuración avanzada + CLI `wcm projects set-max-pages ID N`.
- **ADR-052** — Endpoint `/summary` devuelve `pages_with_many_unknowns`. Badge ámbar en `ProjectHeader` cuando >0.
- **ADR-053** — `qa_runner` con thresholds independientes a11y/best-practices/seo (env vars `LIGHTHOUSE_*_MIN_CRITICAL`) + fórmula proporcional broken links (`max(BROKEN_LINKS_MIN_ABSOLUTE, total * BROKEN_LINKS_RATIO_THRESHOLD)`).
- **ADR-054** — Endpoint `DELETE /api/v1/projects/{id}` admin-only con confirmación literal `{"confirm": "DELETE PROJECT N"}`. 409 si status=running. UI con input que valida el texto exacto antes de habilitar el botón. CLI `wcm projects delete ID --confirm "DELETE PROJECT N"`.

### Changed

- **ADR-037** — Preflight: Bricks bloqueante (con WPML opcional). Sin tema Bricks, no se permite Start.
- **ADR-048** — `POST /projects/{id}/start` ahora SIEMPRE re-ejecuta preflight (no cachea). Garantiza que el operador no arranque con un destino que cayó entre creación y arranque.
- CLI `wcm projects resume` ya no fuerza re-ejecutar todo — opt-in con `-f`.
- `api.delete` (dashboard) acepta body opcional (necesario para DELETE con `{"confirm": ...}`).

### Database

- `0009_pre_deploy_snapshot.py` — `projects.pre_deploy_snapshot_path TEXT NULL` + `_at TIMESTAMPTZ NULL`.
- `0010_visual_diff_threshold.py` — `projects.visual_diff_threshold FLOAT NULL CHECK 0..1`.
- `0011_woo_orders.py` — Tabla nueva con PII cifrada + índice `(project_id, migrated_at)`.
- `0012_max_pages_scrape.py` — `projects.max_pages_scrape INT NULL CHECK 1..500`.

### Decisions (ADRs nuevos)

ADR-037 a ADR-054 (18 ADRs). Detalle completo en `docs/decisiones.md`.

### Tests

- 858 pytest verde (apps + packages + cli, ignorando integration).
- 276 vitest verde (32 archivos).
- Ruff + ESLint + tsc verde.

### Dependencies

- Sin nuevas dependencias Python ni TS (todo construido sobre la stack existente).

---

## [0.19.0] — 2026-05-19

Sprint MINOR: **reactividad sub-segundo + rollback + Hostinger
mejorado + vista fleet**. Cuatro ejes que cierran la deuda visual y
operativa antes del primer piloto real.

### Added

- **SSE backend** — `apps/api/src/wcm_api/services/events.py` con
  `channel_for(id)`, `subscribe_to_project_events(id)`, `format_sse`,
  heartbeat 25s. Endpoint `GET /api/v1/projects/{id}/events`
  (`text/event-stream`). 503 si Redis no disponible (cliente cae a
  polling).
- **Worker publisher** — `apps/worker/src/wcm_worker/integrations/events.py`
  con `publish_phase_event(project_id, phase_name, status)`. Llamado
  desde `_mark_phase()` del orchestrator. Silencioso si Redis falla
  (el pipeline NUNCA rompe por canal SSE caído).
- **SSE frontend** — `ProjectPoller` refactor: abre EventSource, cada
  mensaje dispara `router.refresh()`. Si conexión falla (onerror +
  readyState=CLOSED) cae automáticamente a polling 2s tradicional.
  Banner muestra modo activo (`stream SSE` vs `polling 2s`).
- **Status `ROLLED_BACK`** en `ProjectStatus` enum. La columna VARCHAR
  acepta el nuevo valor sin migración.
- **`RollbackAgent`** (`apps/worker/src/wcm_worker/agents/rollback.py`):
  itera `bricks_pages.wp_post_id NOT NULL`, hace `DELETE
  /wp/v2/pages/{id}?force=true` vía REST. Idempotente: si un DELETE
  falla, continúa con el siguiente y permite re-ejecución.
- **Endpoint `POST /api/v1/projects/{id}/rollback`** (operator+).
  Requiere `{"confirm": true}` en body. Solo permitido si status ∈
  {qa_failed, completed, blocked_human_input}.
- **UI rollback**: botón "Rollback" (icon Undo2) en ProjectActions
  con confirmación inline en rojo (sin `window.confirm`). Status
  `rolled_back` se muestra como "proyecto revertido".
- **CLI `wcm projects rollback ID [--yes/-y]`** con prompt interactivo
  por defecto (typer.confirm). Sugiere `wcm projects watch ID` para
  seguir progreso.
- **Extractor Hostinger AI mejorado**: form fields canónicos con
  data-role/data-field-type (Hostinger moderno) + fallback heurístico.
  Theme estructurado: `result.theme_colors` y `result.theme_fonts`
  como dict (antes solo nota). Contact info: `result.contact_info`
  con email/phone/social estructurados desde footer.
- **Fixture nueva** `tests/fixtures/hostinger/restaurante.html`
  (Casa Pepa) con form moderno + contact + theme vars.
- **Endpoint `GET /api/v1/projects/fleet`** (any_user). Devuelve
  todos los proyectos con `phase_summary` pre-agregada en 5 buckets
  canónicos. Una sola query (sin N+1 fetches del cliente).
- **`ProjectsFleetGrid`** dashboard: grid 1/2/3 cols con tarjetas
  por proyecto. Mini-stepper de 5 dots conectados (scrape/transpile/
  deploy/qa/notify) con animate-pulse en running. FeaturePills
  (Woo/WPML/builder) + DiffScoreBadge en footer.
- **ViewToggle `/projects?view=fleet|table`** preservando filtro
  status entre vistas. Default sigue siendo `table`.

### Changed

- **Botón "+ Nuevo proyecto"** en `/projects` ahora apunta a
  `/projects/new` (wizard v0.18.0) en lugar de `/leads`.
- **Pipeline orchestrator** publica eventos SSE tras cada `_mark_phase`.

### Decisions

- **Polling como fallback, no sustitución**: SSE preferido pero
  polling 2s queda activo automáticamente si Redis no responde. UX
  graceful: el banner muestra qué modo está activo.
- **`_aggregate_bucket_status` prioridad**: failed > running >
  pending > completed (todas) > skipped. Razón: en un dashboard de
  fleet, el rojo (failed) debe destacar inmediatamente, el running
  con pulse debe llamar la atención secundaria.
- **Rollback MVP sin snapshot**: solo borra las páginas creadas por
  wp-deployer; NO restaura cambios a páginas existentes. Suficiente
  para el escenario común "deploy salió mal, quiero empezar limpio".
  Snapshot SQL completo queda para v0.20.0+ si surge necesidad real.
- **Hostinger sin API de admin oficial** (confirmado): el sprint
  invierte en mejorar el extractor de scraping en lugar de adapter
  API (que no existe).

### Tests

- **Backend**: +33 (events service 6, events endpoint 4, events
  publisher 5, rollback agent 5, rollback endpoint 6, fleet endpoint
  12 - 5 helpers ya contados). Total Python: **788 verde** (10 skipped).
- **Dashboard**: +13 vitest (project-poller 5, projects-fleet-grid 8).
  Total: **274 verde**.
- **Scraper-core**: +6 (form estructurado/fallback, theme dict,
  contact estructurado/fallback). Suite scraper-core 24/24 verde.
- **CLI**: +4 (rollback con --yes, sin --yes confirma/cancela,
  409 propaga).

### Acción pendiente del operador (despliegue)

- `REDIS_URL` debe estar configurada en `.env` del API y del worker
  (ya lo estaba para Celery). Sin ella, SSE devuelve 503 y el
  dashboard cae a polling 2s — funcional pero menos elegante.
- Para que el rollback funcione, el WP destino debe seguir respondiendo
  a las credenciales `WP_DEFAULT_REST_*` del deploy original.

### Siguiente

- v0.20.0 candidatos: snapshot SQL pre-deploy para rollback robusto,
  adapter API si Hostinger publica una, paginación en endpoint /fleet
  cuando crezca el catálogo.

---

## [0.18.0] — 2026-05-19

Sprint MINOR: **vista viva del pipeline + onboarding asistido +
acceso al back del origen (Wix / Webflow)**. Tres ejes que faltaban
para que el operador pueda usar el producto en su día a día sin
recargar manualmente, sin fallar a mitad del pipeline por configs
ausentes, y aprovechando credenciales API del origen cuando el
cliente las da.

### Added

- **Vista viva del pipeline** — `PipelineStepper` horizontal de 15
  segmentos con iconos por status (Check verde, Loader2 spin lima,
  Circle gris, X rojo, SkipForward ámbar). Tooltip CSS-only con
  duración + summary + error truncado. Scroll-x con snap en mobile.
  `ProjectPoller` cliente con `setInterval(router.refresh, 2000)`
  activo solo si status ∈ {queued, running}. Banner "vista viva ·
  actualiza cada 2s" en las 4 sub-páginas del proyecto.
- **Migración Alembic 0008** — `0008_source_creds_preflight.py`. Añade
  a `projects`: `source_access_mode` (CHECK none/api/full, default
  none), `source_credentials_encrypted` (Fernet TEXT), `preflight_results_json`
  (JSONB cache), `preflight_at` (TIMESTAMPTZ).
- **Endpoint `POST /api/v1/projects/{id}/preflight`** — ejecuta 4
  chequeos en paralelo con `asyncio.gather` (timeout 10s c/u):
  1. WP destino accesible (REST + SSH TCP banner) — BLOQUEA si falla.
  2. Plugins (Bricks/GF/WC vía HEAD `/wp-json/{}/`) — informativo.
  3. Origen accesible (GET source_url) — BLOQUEA si 4xx/5xx.
  4. Credenciales del origen (Wix/Webflow API ping) — warning, NO
     bloquea (pipeline cae a scraping Playwright público).
  Persiste resultado en `projects.preflight_results_json` + `preflight_at`.
- **Endpoint `PUT /api/v1/projects/{id}/source-credentials`** (admin-only)
  con schema discriminado por builder (Wix vs Webflow). Cifra con
  Fernet antes de persistir. NUNCA devuelve credenciales en claro;
  `ProjectRead.has_source_credentials` solo expone el flag.
- **Endpoint `DELETE /api/v1/projects/{id}/source-credentials`** vuelve
  a modo `none` y limpia el ciphertext.
- **Adapter Wix REST v3** (`apps/worker/src/wcm_worker/integrations/wix_api.py`):
  `WixApiClient` async con `list_page_urls()` que devuelve URLs canónicas
  combinando `/site-properties/v4/properties` + `/site-pages/v1/pages`.
  Errores tipados: `WixApiAuthError`, `WixApiNotFoundError`,
  `WixApiRateLimitError`. `list_products()` stub para v0.19.0+.
- **Adapter Webflow Sites API v2** (`webflow_api.py`): espejo del Wix.
  Combina `/sites/{id}` + `/sites/{id}/pages`. Fallback a subdominio
  `*.webflow.io` si no hay `customDomain`. `list_collections()` stub.
- **Branching en `scraper-origin`**: si `project.source_access_mode='api'`
  y credenciales descifrables → siembra el BFS con las URLs canónicas
  de la API. Si falla por cualquier motivo (auth/network/descifrado)
  → cae al BFS tradicional sin propagar. Mejor cobertura: detecta
  páginas no enlazadas desde el menú público.
- **Wizard `/projects/new` 4 pasos** (sustituye al `ConvertToProjectDialog`):
  1. Origen + builder + credenciales opcionales (panel se muestra solo
     si builder ∈ {wix, webflow}).
  2. Destino + nota sobre env vars WP_DEFAULT_*.
  3. Features (e-commerce / multilang / preserve_paths).
  4. Crear + Preflight visual con `<PreflightDisplay>` (4 cards grid
     2x2 + lista de blocking_issues + warnings) → "Crear y arrancar"
     deshabilitado hasta `can_start=true`.
  Pre-rellena desde `?lead_id=N` si viene.
- **Componente `PreflightDisplay`**: 4 cards visuales reutilizables.
  Verde lima OK / rojo bloqueante / ámbar aviso / gris pendiente.
  Plugins card con counter `presentes/total`.
- **CLI v0.18.0**:
  - `wcm projects preflight ID` — ejecuta los 4 checks, imprime cada
    uno con icono ✓/✗/⚠ y devuelve exit code 1 si `can_start=false`.
  - `wcm projects watch ID [--interval 2.0]` — Rich `Live` panel con
    stepper 15 fases actualizándose hasta status terminal. Ctrl+C limpio.
  - `wcm projects set-source-credentials ID --builder wix|webflow
    --api-key/--api-token X --site-id Y` — admin-only. NUNCA imprime
    credenciales en stdout.
- **Helpers Fernet duplicados**: API
  (`apps/api/src/wcm_api/services/source_credentials.py` con encrypt+decrypt)
  y worker (`apps/worker/src/wcm_worker/integrations/source_credentials.py`
  solo decrypt). Extraer a paquete compartido es scope futuro.

### Changed

- **`ConvertToProjectDialog` eliminado**. El botón "Convertir a
  proyecto" del lead navega a `/projects/new?lead_id=N`.
- **`ProjectHeader`** acepta prop nueva `phases?: ProjectPhaseRead[]` y
  renderiza `<PipelineStepper>` debajo de la `PhaseProgressBar` cuando
  está disponible.
- **`Project.has_source_credentials`** — `@property` derivada de
  `source_credentials_encrypted` para exponer el flag sin revelar el
  ciphertext (Pydantic con `from_attributes=True` lo recoge).

### Decisions

- **Polling 2s vs SSE**: elegimos polling con `router.refresh()` por
  simplicidad y compatibilidad con SSR de Next 15. SSE queda planificado
  pero fuera de sprint.
- **Wix Headless / REST v3 únicamente** (no Wix clásico XML). Documentado
  como limitación.
- **Credenciales del origen siempre admin-only**: PUT/DELETE requieren
  rol admin (no operator). Razón: son secretos del cliente.
- **Fernet duplicado en API + worker**: pragmático (30 LOC × 2)
  vs. paquete compartido (over-engineering en v0.18.0).
- **Cifrar credenciales antes de persistir**: trade-off conocido — si
  el operador rota `FERNET_KEY` hay que re-introducirlas. Mismo riesgo
  que `deploy_credentials_encrypted`.

### Migración

- `0008_source_creds_preflight.py` — 4 cols nuevas en `projects`. Sin
  downtime, default `none` para `source_access_mode` (compatible con
  proyectos existentes).

### Tests

- **Backend**: +30 (preflight router 6, source-credentials router 7,
  source-credentials service 5, Wix API 9, Webflow API 8, scraper-origin
  branching 6). Total Python: **741 verde** (10 skipped).
- **Dashboard**: +18 vitest (pipeline-stepper 6, preflight-display 6,
  new-project-wizard 6). Total: **261 verde**.
- **CLI**: +7 (preflight + set-source-credentials con todas las
  validaciones de CLI flags).

### Acción pendiente del operador (despliegue)

- Aplicar migración 0008: `alembic upgrade head` con
  `DATABASE_SYNC_URL` apuntando a Postgres del entorno.
- Configurar `FERNET_KEY` en el `.env` del API y del worker (misma
  clave): `python -c 'from cryptography.fernet import Fernet;
  print(Fernet.generate_key().decode())'`. Sin ella, el PUT
  /source-credentials devuelve 503 (graceful).
- Para probar adapters Wix/Webflow end-to-end: lead piloto + API key
  real de uno de los dos builders. Sin esto el bloque D va con mocks
  pero la fase no se valida real.

### Siguiente

- v0.19.0: SSE para reactividad sub-segundo, adapter Hostinger AI,
  vista "fleet" multi-proyecto con stepper resumido.

---

## [0.17.0] — 2026-05-19

Sprint MINOR: **los 3 stubs nicho del pipeline pasan a implementación
real**. Tras este sprint **15/15 fases del pipeline son reales** (vs.
12/15 previas). El flujo de migración cierra su gap funcional y queda
solo trabajo de QA manual + integración con WP destino real.

### Added

- **Agente `woo-migrator` real**
  (`apps/worker/src/wcm_worker/agents/woo_migrator.py`):
  Auto-detecta WooCommerce vía
  `GET /wp-json/wc/v3/system_status/tools`. Si responde 401/403/404 →
  ResidualTask BLOCKING 'instalar WooCommerce' + fase SKIPPED sin
  romper pipeline.
  Si WC disponible:
  - Sin productos en `woo_products` → ResidualTask 'migrar manualmente'.
  - Con productos → upsert categorías por slug (con cache) + upsert
    productos por SKU (`GET /wc/v3/products?sku=...` para detectar,
    POST si no existe / PUT si sí). Persiste `wp_product_id`.
  - **Siempre** crea ResidualTask BLOCKING 'configurar pasarela de
    pago' (Stripe/Redsys/PayPal — requieren credenciales del cliente).
  Fallo individual de producto no para la migración (continúa + warning).
- **Agente `forms-rebuilder` real**
  (`apps/worker/src/wcm_worker/agents/forms_rebuilder.py`):
  Parsea `html_raw` de `scraped_pages` con BeautifulSoup, extrae
  `<form>` con sus campos. Dedupe por título normalizado.
  Mapea HTML5 types → Gravity Forms types (text/email/url/tel/number/
  date/file/hidden, textarea, select con choices del DOM).
  - Sin forms detectados → fase salta sin tocar destino (caso típico
    web corporativa).
  - Forms detectados + Gravity Forms no responde en `/wp-json/gf/v2/`
    → ResidualTask BLOCKING 'instalar Gravity Forms'.
  - GF disponible → lista forms existentes (dedupe), crea los nuevos
    como `inactive` con notificación email al admin (env
    `WP_DEFAULT_NOTIFY_EMAIL` → `COMPANY_CONTACT_EMAIL` →
    `info@webcafeina.com`).
  - ResidualTask CLIENT_CONFIG con resumen + acciones manuales
    (activar forms, insertar shortcodes, configurar integraciones).
- **Agente `wpml-configurator` real**
  (`apps/worker/src/wcm_worker/agents/wpml_configurator.py`):
  Webcafeína NO tiene licencia WPML — decisión arquitectónica.
  Si `project.is_multilang=False` → fase salta limpia.
  Si `is_multilang=True` → SIEMPRE genera UNA ResidualTask BLOCKING
  muy detallada con:
  - Idiomas detectados (primary + secundarios).
  - Páginas agrupadas por idioma (URL origen + slug destino), cap 50/lang.
  - Guía paso-a-paso WPML: adquirir licencia → instalar plugins
    (core + String + Translation + Media) → activar → idiomas +
    switcher → traducciones.
  - Validación final (hreflang, sitemap multi-idioma).
  - Estimación: 30 min base + 5 min por página secundaria.
- **UI dashboard — `FeatureBadges`**
  (`apps/dashboard/src/app/(app)/projects/[id]/_components/feature-badges.tsx`):
  Badges WooCommerce / Gravity Forms / WPML en el header del proyecto.
  Solo aparece el que aplica (`has_ecommerce`, fase rebuild_forms
  ejecutó, `is_multilang`). Color por estado de la fase: verde lima =
  completed, ámbar = skipped con residual, rojo = failed, gris =
  pending. Click navega a `/residual-tasks?generated_by=<agente>`.
  Integrado en las 4 sub-páginas del proyecto.
- **CLI v0.17.0**:
  - `wcm projects woo-status ID` → resumen del agente woo-migrator
    (WC detectado, productos migrados / fallidos).
  - `wcm projects forms-status ID` → resumen del agente
    forms-rebuilder (GF detectado, forms detectados / creados).
  - `wcm projects wpml-status ID` → resumen del agente
    wpml-configurator (idiomas, primary, páginas por idioma) +
    aviso "Webcafeína NO tiene licencia WPML".

### Changed

- **Pipeline 15/15 fases reales**. Se elimina
  `apps/worker/tests/unit/test_agents_stubs.py` — ya no quedan stubs
  (regression test cumplió su misión).

### Decisions

- **WPML sin licencia → residual manual obligatoria**. No instalamos
  ni configuramos nada en el destino. El agente sigue ejecutándose
  para documentar el trabajo pendiente del operador, incluso si
  Webcafeína adquiere licencia en el futuro se puede extender este
  agent para llamar `/wpml/v1/languages`.
- **Detección de plugins por auto-degradación**: tanto WC como GF
  comprueban su disponibilidad vía REST con `GET` que devuelve 404 si
  el plugin no está activo. Decisión: 401/403/404 → "no disponible";
  5xx/network → propagar para investigación. Sin esto el agent
  rompía cuando el WP destino no tenía los plugins instalados (caso
  cliente típico al primer despliegue).
- **forms-rebuilder no es condicional en pipeline** — corre siempre,
  detecta y salta si no hay forms. Razón: la mayoría de webs
  corporativas tienen al menos contacto, no podemos confiar en una
  flag previa del proyecto.
- **Pasarela de pago = residual SIEMPRE** aunque la migración WC
  vaya OK. Las credenciales son del cliente y la pasarela origen
  (Wix Stores típicamente) usa proveedores distintos a los WC
  habituales.

### Tests

- **Backend**: +27 tests (woo 10, forms 10, wpml 7). Total Python:
  **694 verde** (10 skipped). Test `test_agents_stubs.py` eliminado.
- **Dashboard**: +6 vitest (`feature-badges`). Total: **243 verde**.
- **CLI**: +6 tests (`test_projects_status_v017.py`).

### Acción pendiente del operador

Antes de probar el flujo end-to-end con un lead real, asegurarse de
que el WordPress destino tiene los plugins necesarios según el caso:

- **Web corporativa** (típico): Bricks Builder, Gravity Forms.
- **Tienda online**: + WooCommerce.
- **Multilang**: comprar licencia WPML (la guía paso a paso queda
  en el checklist generado por el pipeline).

Cualquier ausencia se detecta automáticamente y genera ResidualTask
clara en el checklist — el pipeline NO rompe.

### Siguiente

Pipeline funcional al 100%. Próximos pasos: QA manual end-to-end con
un lead real corporativo, ajustes según hallazgos del piloto.

---

## [0.16.0] — 2026-05-19

Sprint MINOR: **cierre del flujo de migración** — los 3 agentes
transversales del pipeline (visual-diff + qa-runner + checklist-generator)
pasan de stub a implementación real. Con esto el operador puede defender
visualmente que el destino se parece al origen, pasa QA automático con
Lighthouse + W3C + links + SEO, y entrega al cliente un PDF Webcafeína
con los residuales pendientes. Tras este sprint: 12/15 fases reales
(vs. 9/15 previas). Restan v0.17.0 los 3 stubs nicho (woo-migrator +
forms-rebuilder + wpml-configurator).

### Added

- **Agente `visual-diff` real** (`apps/worker/src/wcm_worker/agents/visual_diff.py`):
  Playwright sync con `screenshot_session()` context manager que reusa
  1 browser + 1 context para N páginas. Captura origen + destino,
  compara con `pixelmatch` (threshold 0.15), genera overlay PNG con
  diferencias en rojo. UPSERT en `visual_diffs` con
  `pg_insert.on_conflict_do_update`. Recalcula `projects.visual_diff_avg_score`.
- **Agente `qa-runner` real** (`apps/worker/src/wcm_worker/agents/qa_runner.py`):
  ejecuta 6 checks — Lighthouse desktop+mobile vía subprocess Node
  (parsing JSON 0-100), validación HTML W3C de hasta 50 páginas con
  throttle 1.2s/req, link checker httpx+bs4 con dedupe del dominio
  (HEAD primero, GET ranged si 405), verificación HTTPS válido,
  robots.txt accesible, sitemap.xml accesible. Genera ResidualTask
  automática por cada fallo crítico (perf<50, html_errors>20,
  broken>5, https inválido, robots/sitemap inaccesibles).
- **Agente `checklist-generator` real** (`apps/worker/src/wcm_worker/agents/checklist_generator.py`):
  carga residuales agrupadas por categoría canónica
  (blocking_go_live → client_config → visual_content → post_go_live
  → other), renderiza Markdown con template Jinja2 + PDF con WeasyPrint
  + CSS Webcafeína-branded (paleta `#B1F100`, A4, page-counter).
  Sube a R2 (`projects/{id}/checklist/{checklist.md|checklist.pdf}`)
  o fallback file:// local. Persiste URLs en `projects.checklist_md_url`
  + `projects.checklist_pdf_url`.
- **Tabla `visual_diffs`** (migración 0007): `(id PK, project_id FK,
  page_path, source/target/overlay_url, score, viewport_width,
  timestamps)` con UNIQUE `(project_id, page_path)` — una fila por
  página, sobrescritura idempotente entre runs.
- **Tabla `qa_reports`** (migración 0007): `(id PK, project_id FK,
  lighthouse_perf_desktop/mobile, lighthouse_a11y_avg,
  lighthouse_best_practices_avg, lighthouse_seo_avg,
  html_validator_errors/warnings_count, broken_links_count,
  total_links_checked, https_valid, robots_accessible,
  sitemap_accessible, report_json JSONB, timestamps)`. Una fila por
  ejecución (la última gana, las antiguas se conservan para histórico).
- **Endpoints API**:
  - `GET /api/v1/projects/{id}/visual-diffs` → list de páginas
    comparadas con score + URLs.
  - `GET /api/v1/projects/{id}/qa-report` → último QA report o `null`.
  - `GET /api/v1/projects/{id}/checklist/download?format=pdf|md` →
    302 a R2 si https, stream local con `content-disposition: attachment`
    si file://.
- **UI dashboard** `/projects/[id]/diff` real: Server Component fetcha
  `visual-diffs` y renderiza `DiffGallery` con thumbnails 3x
  (source/target/overlay) + ScoreBadge (verde ≥85, ámbar 70-85, rojo
  <70). Click abre modal full-size lado a lado. Fallback "(local)" si
  R2 no configurado.
- **UI dashboard** `/projects/[id]/qa` nuevo: Server Component con
  `QaScorecards` — 5 ScoreCards Lighthouse (threshold 80/50), 2
  CountCards HTML W3C, 2 CountCards links, 3 BoolCards SEO/SSL +
  tabla detallada de links rotos si hay >0.
- **Tab "QA"** en `ProjectTabs` con icon `GaugeCircle`.
- **Botones "Descargar PDF" / "MD"** en header de
  `/projects/[id]/checklist` → endpoint download del API.
- **CLI**:
  - `wcm projects diff ID` → tabla con score por página.
  - `wcm projects qa-report ID` → resumen del último QA report.
  - `wcm projects export-checklist ID --out FILE --format pdf|md`
    (era stub) → descarga real siguiendo redirects 302.
- **`ApiClient.get_bytes()`** en cliente CLI: descarga bruta con
  `follow_redirects=True` para entregables binarios.
- **Schemas pydantic**: `VisualDiffRead`, `VisualDiffsListResponse`,
  `QaReportRead` + extensión de `ProjectRead` con
  `checklist_md_url` / `checklist_pdf_url`. Re-exports en
  `shared-types/__init__.py` y `types/api.ts` regenerados.
- **Helpers worker**:
  - `apps/worker/src/wcm_worker/integrations/playwright_screenshot.py`
    — `screenshot_session()` context manager + `PlaywrightNotAvailableError`.
  - `apps/worker/src/wcm_worker/integrations/visual_diff_compare.py`
    — `compare()` con pixelmatch.
  - `apps/worker/src/wcm_worker/integrations/lighthouse.py`,
    `html_validator.py`, `link_checker.py`,
    `pdf_generator.py` (WeasyPrint + markdown-it-py).

### Changed

- **Pipeline**: las 3 fases `visual-diff`, `qa-runner`,
  `checklist-generator` salen del listado de stubs activos
  (`apps/worker/tests/unit/test_agents_stubs.py`). El test verifica
  que NO están registradas como `AgentNotImplementedError`.
- **Plantilla checklist Jinja2** (`apps/worker/src/wcm_worker/templates/checklist/checklist.md.j2`):
  header proyecto + tabla resumen + secciones por categoría + tareas
  con title/status/estimated/generated_by/assignee/ClickUp + footer
  Webcafeína (CIF, dirección, contacto legal).

### Decisions

- **ADR no formal** — degradación grácil masiva: Playwright no
  instalado / WeasyPrint deps SO faltan / Lighthouse no en PATH → la
  fase devuelve summary explicativo + warnings, NO rompe el pipeline.
  Cada caso genera ResidualTask documentada para el operador.
- **R2 ausente → file:// fallback**: el dashboard detecta y muestra
  "(local)" en thumbnails. CLI no se ve afectada (sigue redirects).
- **Categorías canónicas del checklist**: `blocking_go_live` →
  `client_config` → `visual_content` → `post_go_live` → `other`,
  garantizando orden estable en el PDF entregable.
- **Renderer canónico con `string.Template` PEP 292** (sintaxis
  `$nombre`) en pdf_generator para NO chocar con slots `{{ }}` Jinja2
  del composer.

### Migración

- `0007_visual_diff_qa_reports.py` — crea tablas `visual_diffs` y
  `qa_reports` + añade `projects.checklist_md_url` y
  `projects.checklist_pdf_url` (VARCHAR 500 nullable). Una sola
  migración para los 3 cambios del sprint.

### Dependencias

- **apps/worker** añade: `playwright>=1.45`, `pixelmatch>=0.4`,
  `weasyprint>=68.0`, `markdown-it-py>=3.0`.
- **Dependencias SO en servidor producción** (documentar en
  `docs/despliegue.md`):
  - Playwright: `playwright install-deps && playwright install chromium`
  - WeasyPrint: `apt install libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf2.0-0`
  - Lighthouse: `npm install -g lighthouse@^12`

### Tests

- **Backend**: +57 tests (visual-diff 18, qa-runner 21, checklist 18).
  Total Python: **664 verde** (10 skipped).
- **Dashboard**: +12 vitest (`diff-gallery` 6, `qa-scorecards` 6).
  Total: **237 verde**.
- **CLI**: +6 tests (`test_projects_diff_qa.py`).

### Próximo sprint

- **v0.17.0** — los 3 stubs nicho: `woo-migrator` (WooCommerce),
  `forms-rebuilder` (Gravity Forms), `wpml-configurator` (sin licencia
  WPML → siempre residual task). UI con badges de features por
  proyecto. CLI ampliada.

---

## [0.15.0] — 2026-05-19

Sprint MINOR: **editor visual del layout maestro + preview lateral
en plantillas + toolbar Tiptap ampliado**. El operador ya no necesita
saber HTML email-safe para personalizar la marca de los correos —
edita colores, branding, tipografía y espaciado con un form y ve el
resultado en un iframe lateral. Las plantillas individuales también
ganan preview en vivo al lado del WYSIWYG (sin tab).

### Added

- **Tema visual del layout maestro** (`/settings/email-layout` tab
  Visual): form con 24 controles agrupados en Colores · CTA / Colores ·
  Fondo y texto / Branding / Tipografía / Espaciado / Bordes. Cada
  cambio dispara preview en vivo (debounce 600 ms +
  AbortController). Botón "Guardar tema" + "Restaurar valores por
  defecto". Tab "Código" sigue disponible como fallback experto.
- **Singleton `email_layouts.theme_config`** (JSONB nullable) — si
  poblado, el tema visual está activo; si NULL, modo Código manual y
  el tab Visual se deshabilita con tooltip "Restaura el tema por
  defecto para activarlo".
- **Schema `EmailLayoutTheme`** (23 campos pydantic) con validaciones
  HEX 6 chars, bounds numéricos (ancho 320-720 px, padding 8-64 px,
  radius 0-12 px), tipografía Literal email-safe (system-ui / serif /
  Inter). 422 antes de tocar BD.
- **Renderer canónico server-side**
  (`apps/api/src/wcm_api/email_layout_renderer.py`): función pura
  `generate_layout_from_theme(theme) -> (html, css)` usando
  `string.Template` (sintaxis `$nombre`) para NO colisionar con los
  slots `{{ content | safe }}` del composer. Idempotente, testeable.
- **Endpoint `POST /api/v1/email-layout/preview`** (admin,
  rate-limit 60/min): recibe theme y devuelve `{html, css}` sin
  persistir. Alimenta el LivePreview del form Visual.
- **Componente `ColorField`** reutilizable: `<input type="color">`
  nativo + HEX text input sincronizado. Validación cliente regex
  HEX 6 chars — inválido se muestra en rojo pero NO propaga al
  estado para evitar 422 ruidosos.
- **Componente `ThemeEditorForm`** con 24 controles agrupados.
- **Refactor `EmailLayoutEditor`**: tabs custom inline Visual/Código,
  LivePreview compartido (ahora 720 px sticky), botón "Restaurar
  tema por defecto" con `window.confirm`.
- **Preview lateral en `/settings/templates`**: `TemplateForm` y
  `TemplateView` con layout 2-col (`xl:grid-cols-[1fr_500px]`).
  Form actual a la izquierda, iframe preview sticky a la derecha
  que se actualiza con debounce 600 ms a `POST /templates/preview`
  (endpoint nuevo any_user, rate-limit 60/min — genera HTML con un
  payload `OutreachTemplateBase` SIN persistir). Tab "Vista previa"
  del TemplateView ELIMINADO (queda integrado lateral).
- **`RichTextEditor` toolbar ampliado**: extensiones nuevas
  `@tiptap/extension-text-style`, `@tiptap/extension-color`,
  `@tiptap/extension-text-align`. Toolbar añade 3 botones de
  alineación (left/center/right) + botón color de texto (palette
  icon + `<input type="color" sr-only>` que dispara setColor).
  StarterKit con `link: false` para evitar duplicate-extension
  warning.
- **CLI `wcm email-layout theme show/reset/set`**:
  - `show`: imprime `theme_config` JSON pretty. Avisa si NULL.
  - `reset --confirm`: PUT con `DEFAULT_THEME` Webcafeína.
  - `set --cta-bg HEX --font-family Inter ...`: 15 flags para
    modificar campos puntuales. Merge con tema existente o parte de
    defaults si no había.
- **Migración Alembic 0006**: añade `theme_config JSONB NULL` a
  `email_layouts`. Singleton existente queda con NULL (operador
  activa el modo Visual con "Restaurar valores por defecto" desde
  UI o `wcm email-layout theme reset --confirm`).
- **3 deps Tiptap nuevas** (~25 KB gzip extra) @^3.23.4.

### Changed

- `PUT /api/v1/email-layout` ahora acepta 3 modos: solo
  `theme_config` (backend regenera HTML+CSS), solo `layout_html` +
  `layout_css` (modo Código, theme=NULL), o combinación. AuditLog
  ahora distingue `mode: "visual" | "code"` en su payload.
- `EmailLayoutUpdate` schema: `layout_html` y `layout_css` ahora
  `Optional[str]` (antes obligatorios) para soportar modo Visual
  donde el cliente solo manda `theme_config`.
- `EmailLayoutRead` schema: expone `theme_config: EmailLayoutTheme | None`.
- `TemplateView` y `TemplateForm` pasan a layout 2-col interno con
  preview lateral. Mejora notable de UX al editar.
- `RichTextEditor` configura StarterKit con `link: false` (eliminé
  warning de extensión duplicada).

### Decisions

- **`string.Template` (PEP 292) en el renderer canónico** en lugar
  de Jinja2 — para NO colisionar con los slots `{{ ... }}` del
  composer. Output Jinja2-válido sin trucos de DebugUndefined.
- **`<input type="color">` nativo** + HEX text input en vez de
  librería externa de color picker. UX suficiente, 0 KB de bundle
  extra, accesibilidad nativa.
- **Tabs custom inline** (mismo patrón que `template-manager`) sin
  Radix Tabs — el repo no tenía `tabs.tsx` y no merece la pena
  introducir Radix Tabs por esto.
- **Preview server-side con `POST /preview`** (no client-side) para
  garantizar fidelidad entre lo que ves y lo que llegará al lead.
  Cancel obsoletos con AbortController.
- **`TextStyle` + `Color` + `TextAlign` para Tiptap** — output HTML
  email-safe (`<span style="color">`, `<p style="text-align">`).
  Premailer los respeta.
- **Modo Código irreversible sin reset**: si guardas desde tab
  Código, `theme_config=NULL` y el tab Visual queda bloqueado. Solo
  "Restaurar valores por defecto" lo reactiva. Es el invariante
  más sencillo y predecible para el usuario.

### Tests

- **+33 tests nuevos**: 11 renderer canónico (defaults, custom,
  validaciones, idempotencia, edge cases logo), 6 router preview +
  put theme + RBAC + HEX inválido, 6 ThemeEditorForm vitest, 5
  EmailLayoutEditor vitest, 7 CLI theme (show/reset/set/merge).
- Suite global: **599 pytest + 225 vitest = 824 tests verde**.

### Migración Alembic

- `0006_email_layout_theme_config.py`: añade columna `theme_config
  JSONB NULL` a `email_layouts`. Downgrade limpio. Compatible con
  `alembic upgrade head` desde 0005.

### Dependencias

- Frontend: `@tiptap/extension-color@^3.23.4`,
  `@tiptap/extension-text-align@^3.23.4`,
  `@tiptap/extension-text-style@^3.23.4` (~25 KB gzip total).

### Post-release: no requiere acción del operador

- Al aplicar la migración 0006, el singleton existente queda con
  `theme_config=NULL`. Al entrar a `/settings/email-layout` el tab
  Visual aparece deshabilitado. Para activarlo, pulsa "Restaurar
  valores por defecto" (o `wcm email-layout theme reset --confirm`)
  — los defaults Webcafeína se aplican y a partir de ahí editas
  visualmente.
- El PNG del logo (pendiente de v0.14.0) sigue siendo opcional.

---

## [0.14.1] — 2026-05-18

Hotfix: bug del FK `email_layouts.updated_by_user_id` declarado como
`Integer` cuando `users.id` es `UUID`. La migración 0005 fallaba al
aplicarse en Postgres real. Corregido modelo + migración + schema +
endpoint. Sin breaking changes.

---

## [0.14.0] — 2026-05-18

Sprint MINOR: **correos de outreach HTML estilados de marca**. Hasta
ahora el composer enviaba texto plano sin formato; ahora el operador
puede formatear visualmente con un editor WYSIWYG, ver el HTML final
en un iframe, y mandar correos de prueba a su propio email antes de
aprobar el envío real al lead. Toda la marca Webcafeína (logo, paleta
lima, CTA estilado, footer legal LSSI) se aplica automáticamente vía
un layout maestro editable.

### Added

- **Pipeline HTML completo** en `outreach_composer` →
  `outreach_sender` → Resend. El composer renderiza el cuerpo HTML
  (Tiptap output o fallback wrap del texto plano), lo inyecta en el
  layout maestro, aplica premailer para inline CSS, deriva el texto
  plano para clientes sin HTML, y persiste ambos en
  `OutreachSend.body_rendered` + `body_html_rendered`.
- **Singleton `email_layouts`** (tabla nueva con `CHECK id = 1`) con
  la shell HTML maestra editable desde `/settings/email-layout` (UI +
  CLI). Seed inicial email-safe (tabla 600px, header logo, slot
  `{{ content | safe }}`, CTA condicional, footer LSSI).
- **3 columnas opcionales en `outreach_templates`**:
  `body_html_template` (Jinja2 HTML), `cta_label`, `cta_url`. Si
  body_html_template es NULL el composer cae al body_template texto.
- **Snapshot HTML del envío** en `outreach_sends.body_html_rendered`.
  NULL para sends pre-v0.14.0; el preview endpoint re-renderiza
  on-the-fly en ese caso.
- **2 valores nuevos en AuditAction**: `TEST_SEND` y
  `EMAIL_LAYOUT_UPDATE`.
- **3 endpoints API nuevos**:
  - `GET /api/v1/email-layout` + `PUT /api/v1/email-layout`
    (admin-only) con validación Jinja2 antes de persistir.
  - `GET /api/v1/templates/{id}/preview` — render con datos demo.
  - `GET /api/v1/outreach/sequences/{id}/steps/{idx}/preview` y
    `POST .../test-send` (operator/admin, rate-limited 10/min) con
    AuditLog `TEST_SEND` sin mutar el sequence.
- **3 componentes UI nuevos** (`apps/dashboard/src/components/`):
  - `RichTextEditor` — Tiptap SSR-safe con toolbar (bold/italic/link/listas).
  - `EmailPreviewIframe` — iframe sandbox con HTML inlined del API.
  - `TestSendDialog` — modal con input email + envío real.
- **Nueva pantalla `/settings/email-layout`** con editor HTML/CSS
  side-by-side + iframe preview en vivo (debounce 600ms).
- **Card "Layout del correo"** en `/settings`.
- **Tab "Vista previa"** en `/settings/templates` por plantilla.
- **CLI**: `wcm outreach preview SEQ_ID STEP_IDX [--open]`,
  `wcm outreach test-send SEQ_ID STEP_IDX --to EMAIL`,
  `wcm outreach templates preview TPL_ID [--open]`,
  `wcm email-layout show/update`.
- **Script `scripts/upload_email_logo.py`** que sube el PNG del
  logo a R2 (`branding/webcafeina-email-logo.png`) e imprime la URL
  para `.env` como `EMAIL_LOGO_URL`.
- Helpers `wcm_worker.integrations.html_email` (inline_css,
  html_to_text con expansión `<a href>` → `texto (url)`,
  wrap_plain_as_html, is_html) y
  `wcm_worker.integrations.email_layout` (load_layout con fallback,
  render_full_email).

### Changed

- `OutreachTemplate{Base,Create,Update,Read}` schemas extendidos
  con `body_html_template`, `cta_label`, `cta_url`.
- `OutreachSendRead` añade `body_html_rendered`.
- `PATCH /templates/{id}` usa `exclude_unset=True` en el dump del
  payload — permite vaciar campos enviando `null` explícito.
- `outreach_sender.py` inyecta `body_html=send.body_html_rendered`
  al `ResendClient.send()` cuando no es NULL.
- Editor del step del lead pasa de textarea font-mono a Tiptap
  WYSIWYG. Tests adaptados mockeando Tiptap como textarea.
- `lib/api.ts` y `cli/client.py` añaden helper `put()`.

### Decisions

- **Layout singleton** en lugar de columnas duplicadas por plantilla
  — el layout es compartido, una sola fuente de verdad.
- **CTA por plantilla**, no por step. Si en el futuro se necesita CTA
  por step, añadir columnas a `OutreachStep` (WCM no creado todavía).
- **Validación legal sobre text derivado** (no sobre HTML markup) —
  desacopla las reglas LSSI-CE del formato del correo.
- **`html_to_text` expande `<a href>` como `texto (url)`** para que
  el text/plain part conserve URLs (opt-out, CTA, website) y la
  re-validación legal encuentre el `opt_out_url_base` substring.
- **Test-send NO crea OutreachSend** ni muta el sequence — solo
  Resend directo + AuditLog. Evita contaminar métricas/tracking.
- **Tiptap SSR-safe** con `immediatelyRender: false` (Next.js 15 RSC).

### Tests

- **+65 tests nuevos** (15 BD/schemas, 24 worker HTML pipeline +
  sender, 18 API endpoints, 14 dashboard, 8 CLI).
- Suite Python: **403 tests verde**. Vitest: **214 tests verde**.

### Migración Alembic

- `0005_email_html_layout.py`: añade 3 cols a `outreach_templates`
  (`body_html_template`, `cta_label`, `cta_url`), 1 col a
  `outreach_sends` (`body_html_rendered`), crea tabla singleton
  `email_layouts` con seed inicial. Downgrade limpio.

### Dependencias

- `premailer>=3.10.0` en worker (inline CSS).
- `beautifulsoup4>=4.12` en worker (html_to_text, ya estaba transitiva).
- `@tiptap/react@^3.23.4` + starter-kit + extension-link +
  extension-placeholder en dashboard (~80 KB gzip).

### Post-release: pendiente operador

1. Subir el PNG del logo a `apps/api/assets/webcafeina-email-logo.png`
   (~600 px ancho, transparente, oscuro para fondo blanco) y ejecutar
   `python scripts/upload_email_logo.py`. Copiar la URL impresa a
   `.env` como `EMAIL_LOGO_URL` y reiniciar API + worker.
2. Editar las plantillas existentes (`wix_intro_es`, `followup_es`)
   desde `/settings/templates` para añadir `body_html_template` con
   versión HTML del mensaje + opcionalmente CTA (`Reservar 20min` →
   URL de Cal.com).
3. Hacer un test-send a `info@webcafeina.com` para validar visualmente
   antes de aprobar el primer envío real con marca.

---

## [0.13.3] — 2026-05-18

Banner reactivo en el detalle del lead — refleja el estado real de
la sequence en vez del `lead.status` estático. Cambio UX pedido tras
notar que "Borrador de contacto preparado" se quedaba visible aunque
el operador hubiera aprobado los correos.

### Changed

- **`DraftBanner` ahora Client Component** que fetcha la sequence
  más reciente del lead (`/api/v1/outreach/sequences?lead_id=N&limit=5`)
  con polling cada 4s. Decide internamente si renderizarse y con qué
  copy/color/CTA según el `sequence.status`:

  | Status | Color | Copy | CTA |
  |---|---|---|---|
  | DRAFT_PENDING_REVIEW + legal_passed | ámbar | "Borrador de contacto preparado" | Revisar → |
  | DRAFT_PENDING_REVIEW + !legal_passed | rojo | "Borrador NO aprobable" | Editar → |
  | READY | lima | "Correos listos para enviar" | Enviar → |
  | IN_PROGRESS | lima animado | "Enviando contacto" | Ver progreso → |
  | PAUSED | ámbar | "Contacto pausado" | Reanudar → |
  | COMPLETED | gris | "Contacto completado" | Ver historial → |
  | CANCELLED / OPTED_OUT | — | no se renderiza | — |

- **`lead-detail-pane.tsx`** ya no condiciona el banner a
  `lead.status === "outreach_prepared"`. El banner se monta siempre
  y decide solo (incluyendo no-renderizar cuando no hay sequence o
  el estado es terminal).

### Why

`lead.status` solo cambia cuando el composer genera el draft
(`outreach_prepared`) o cuando el sender envía (`outreach_sent`),
pero NO refleja transiciones intermedias de la sequence (approve,
pause, cancel). El banner usaba ese flag y se quedaba congelado en
"Borrador preparado" aunque el operador ya hubiera aprobado.

Acoplar el banner al `sequence.status` (con polling) lo hace
reactivo a TODAS las acciones del operador en `ContactSequencePanel`
sin necesidad de Context o lifting state.

### Tests

- 203 vitest (+11 nuevos del banner reactivo cubriendo 7 estados +
  edge cases: sin sequence, fetch falla, case uppercase tolerance).
- tsc + lint verde.

---

## [0.13.2] — 2026-05-18

Hotfix de bug crítico detectado al hacer envío real de email tras
v0.13.1. Los OutreachSend quedaban como `QUEUED` indefinidamente en
BD aunque Resend rechazaba el envío con error claro ("domain not
verified" en el caso del usuario). UI mostraba "en cola" sin pista.

### Fixed

- **`OutreachSenderAgent` perdía el estado FAILED** por interacción
  con `session_scope`: el agent marcaba `send.status = FAILED` con
  `flush()` y luego lanzaba `OutreachSenderError`. El context manager
  del wrapper hace `rollback()` ante excepción → el FAILED se perdía.
  Fix: `session.commit()` ANTES del raise en los 3 paths de error
  (Resend rechaza, lead sin email, lead opted-out). Tras el commit
  el rollback del context manager no encuentra cambios pendientes
  — el FAILED queda persistido.
- **Mensaje del error proveedor invisible al operador**. Nuevo
  campo `error_message: str | None` (max 1000) en `OutreachSend` +
  migración Alembic 0004. El agent persiste el mensaje legible
  ("Resend rechazó: domain not verified"). UI `SendTracking` muestra
  una caja roja con el error bajo cada send fallido.
- **AuditLog UPDATE** con `payload={outcome: "failed", provider:
  "resend", error: ..., step_index}` cuando Resend rechaza.
  Trazabilidad RGPD + debugging.

### Verificación manual end-to-end

- **Path SENT verificado en vivo**: send a `info@webcafeina.com` →
  `SENT` con `provider_message_id` real de Resend → email
  entregado.
- **Path FAILED** (teórico, cubierto por preflight): cubierto por el
  fix transaccional. Cuando Resend rechace (ej. dominio externo
  no verificado), el send queda como FAILED + `error_message`
  poblado.

### Tests

- 356 pytest verde.
- 192 vitest + 3 skipped.
- Migración 0004 aplicada en dev local sin issues.

### Acción del operador (no es bug del producto)

Resend exige verificar el dominio "From" por DNS antes de aceptar
envíos a dominios externos. Si `webcafeina.com` no está verificado
en [resend.com/domains](https://resend.com/domains), envíos a
direcciones externas fallarán con `"domain not verified"`. Tras este
hotfix el operador ve la causa directamente en la UI de cada send
fallido.

### Migración Alembic obligatoria pre-deploy

```
alembic upgrade head
```

Aplica la migración 0004 que añade la columna `error_message` a
`outreach_sends`. Sin esto el código nuevo del agent fallará al
intentar SET error_message en una fila con esa columna inexistente.

---

## [0.13.1] — 2026-05-18

Hotfix de CI: 3 tests del CLI fallaban en GitHub Actions tras publicar
v0.13.0 aunque pasaban en preflight local. Causa raíz: ancho del
terminal distinto entre macOS local (~200 cols) y runner GitHub
(80 cols). Rich envolvía la palabra `--confirm` entre líneas y los
asserts substring fallaban.

### Fixed

- **Conftest CLI** (`cli/tests/conftest.py`) fija ahora env vars de
  presentación con monkeypatch autouse:
  - `COLUMNS=200` + `LINES=50` — terminal ancho.
  - `NO_COLOR=1` + `TERM=dumb` — sin escape ANSI.

  Garantiza que el output formateado por typer +
  `rich_markup_mode="rich"` sea bit-a-bit idéntico local y CI.
  Verificado simulando `COLUMNS=80` en el shell — el monkeypatch
  sobreescribe y los 3 tests pasan.

- Tests afectados (sin cambio de assertion, solo conftest):
  - `cli/tests/unit/test_leads_commands.py::test_delete_lead_requires_confirm`
  - `cli/tests/unit/test_outreach_commands.py::test_cancel_requires_confirm`
  - `cli/tests/unit/test_users_commands.py::test_delete_requires_confirm`

### Decisions

- **Reproducibilidad ENV antes que asserts laxos**: la alternativa
  era hacer los asserts más permisivos (`re.search` con `\s*`).
  Rechazada — esconde el síntoma sin arreglar la causa. Cualquier
  futuro test del CLI sufriría el mismo bug. Normalizar el entorno
  una vez es más sostenible.
- Lección persistida en memoria de Claude
  (`feedback_preflight_ci_reproducible.md`) para que cualquier
  sesión futura aplique el patrón sin pasar por el mismo bug.

### Tests

- 356 pytest verde local con la fixture en su sitio. Esperado verde
  en CI (acción de GitHub) ya que la fixture normaliza el entorno
  identico al local.

---

## [0.13.0] — 2026-05-18

Cierre completo de paridad funcional **API ↔ CLI ↔ UI** tras
auditoría exhaustiva. Elimina 3 vaporwares confirmados y rellena
3 GAPs operativos. 7 bloques granulares.

### Fixed (vaporwares eliminados)

- **"Convertir a proyecto" disabled con "Fase 7 producto"** — el
  endpoint `POST /api/v1/projects` SÍ existía. Ahora el botón abre
  `ConvertToProjectDialog` modal con form pre-rellenado desde el
  lead (client_name, target_domain opcional, builder_source auto,
  flags has_ecommerce/is_multilang/preserve_paths) → POST → redirect
  a `/projects/{id}`. Bloqueado solo si lead DISCARDED o OPTED_OUT.
- **"Marcar opt-out" disabled con "Endpoint pendiente"** — el
  endpoint `POST /leads/{id}/consent` con `action=objection_received`
  SÍ existía. Ahora el botón abre `MarkOptOutDialog` con campo nota
  libre (1000 char). Lead pasa a MANUAL_REVIEW + AuditLog OPT_OUT.
  Microcopy distingue entre opt-out manual (este flujo) vs automático
  (link público `/opt-out?token=…` sin auth).
- **OperationRunbook decía "vía CLI wcm users …" que NO EXISTÍA** —
  doble engaño: prometía un CLI inexistente Y endpoint expuesto sin
  acceso. Ahora hay CLI real Y UI real (siguientes secciones).

### Added

- **CLI `wcm users`** completo (6 comandos): list, create
  (genera password aleatorio si se omite, >=18 chars), set-role,
  activate/deactivate (reversible), delete --confirm (irreversible).
  10 tests pytest.
- **API `PATCH /api/v1/users/{id}`** admin-only para cambiar
  role/is_active/name (email no editable; password vía flujo
  separado). Schema `UserUpdate` con 3 campos opcionales.
- **UI `/admin/users`** admin-only con:
  - Tabla densa: email mono | nombre | role select inline | toggle
    activo clickeable | alta relativa | botón Borrar.
  - `CreateUserDialog` modal: email/name/role + checkbox "Generar
    password aleatorio" (recomendado) con `crypto.getRandomValues`
    (alfabeto 73 chars × 18 longitud). Si checked, password se
    muestra al creador en toast de 30s para canal seguro.
  - Mutaciones optimistas (PATCH/DELETE) con toast.
  - Forbidden state amigable si el usuario actual no es admin.
- **UI `/audit-log`** vista completa con filtros (action / entity_type
  / actor / since ISO / limit). Tabla densa con badges por acción
  (9 colores), payload inline (3 pares + "+N más" con hover JSON
  pretty), base legal. Empty state según hay filtro o no.
- **UI `/contactos`** vista global cross-lead de todas las
  secuencias. KpiStrip 5 KPIs (Total, Borrador pendiente con accent
  si >0, Lista para enviar accent, Enviando, Completadas) +
  FilterChips por status. Tabla con Lead # | Negocio + URL |
  Plantilla | Estado badge castellano | Legal ✓/✗ | Creada | Abrir →
  (link a `/leads?selected=N#outreach`). Empty state con CTA a
  `/leads` para componer el primero.
- **Sidebar nav** amplía con 2 entradas: "Contactos" (icon Mail) y
  "Audit log" (icon FileText). `/admin/users` accesible desde
  `/settings` card (no en sidebar — admin-only).

### Changed

- **OperationRunbook** de /settings reescrito: el copy "no hay UI
  prevista; CLI wcm users en el servidor" se sustituye por link
  directo a `/admin/users` + sigue documentando CLI para
  scripts/automatización. Paso 4 nuevo: deactivate / delete
  --confirm. Test "no promete vaporware" reformulado para verificar
  que el link a /admin/users existe en el DOM.
- **Card "Usuarios del sistema"** añadida a `/settings` con link a
  `/admin/users` (al lado de Plantillas de contacto).

### Tests

- 356 pytest API+worker+CLI (+10 nuevos CLI users).
- 192 vitest dashboard + 3 skipped React 19 (sin nuevos componentes
  con tests dedicados — el manager admin se cubrirá en sprint
  futuro junto con guards de role).
- ruff + tsc + lint verde.

### Matriz funcional tras v0.13.0

| Capacidad | API | CLI | UI |
|---|---|---|---|
| **Leads** completo | ✅ | ✅ | ✅ |
| **Convertir a proyecto** | ✅ | ✅ | ✅ **+nuevo** |
| **Opt-out manual** | ✅ | n/a | ✅ **+nuevo** |
| **Outreach sequences** | ✅ | ✅ (v0.12.1) | ✅ (v0.12.1) |
| **Templates Jinja2** | ✅ | ❌ (no priorizado) | ✅ |
| **Proyectos** | ✅ | ✅ | ✅ |
| **Campañas** | ✅ | ✅ | ✅ |
| **Residual tasks** | ✅ | ✅ | ✅ |
| **Errors** | ✅ | n/a | ✅ |
| **Audit log** | ✅ | n/a | ✅ **+nuevo** |
| **Users CRUD** | ✅ | ✅ **+nuevo** | ✅ **+nuevo** |
| **Settings + Firma** | ✅ | n/a | ✅ |

Paridad casi total. Solo gap residual: CLI templates (no urgente —
caso típico es UI). Eliminados los 3 vaporwares "Fase X" históricos.

---

## [0.12.1] — 2026-05-18

Hotfix + cierre del flujo §8 paso 6 (revisar/aprobar/enviar contacto)
tras E2E manual del usuario. 3 problemas reportados, 4 features
añadidas para que el flujo end-to-end funcione tanto en UI como en CLI.

### Fixed

- **Aprobar no transicionaba a READY en la UI** aunque el backend SÍ
  cambiaba el status. Causa: `ContactSequencePanel` es Client con
  `sequences[]` en useState; `router.refresh()` re-renderiza el
  Server padre pero NO re-monta el Client child (`useEffect` con
  `[leadId]` no se re-evalúa). Fix: `replaceSequence` actualiza la
  sequence editada en el state local con la response del POST. UI
  consistente sin depender del refresh del Server.
- **Status badges mostraban el enum en bruto** (`DRAFT PENDING REVIEW`
  uppercase) en vez de castellano. Fix: helpers
  `sequenceStatusLabel()` y `sendStatusLabel()` en `labels.ts` con
  mapeo explícito ("Borrador pendiente", "Lista para enviar",
  "Enviando", "Rebotado", etc.). `SequenceStatusBadge` y
  `SendStatusBadge` usan los helpers. Cero enum visible al usuario.

### Added

- **Botones de acción completos** según status de la sequence en
  `ContactSequencePanel`:
  - DRAFT_PENDING_REVIEW → Aprobar + Cancelar (+ Editar paso).
  - PAUSED → Reanudar + Cancelar.
  - READY → Enviar + Pausar + Cancelar.
  - IN_PROGRESS → Pausar + Cancelar.
  - COMPLETED / OPTED_OUT / CANCELLED → solo lectura ("Sin acciones
    disponibles en estado X").
  - Aprobar visible pero disabled con tooltip si !legalPassed
    (dirige a editar el paso problemático).
- **Botón "Enviar ahora →"** dispara `POST /sequences/{id}/send` →
  crea OutreachSends en estado QUEUED. Tooltip explícito sobre el
  fallback "skipped" cuando RESEND_API_KEY no está configurado.
- **Vista de tracking de envíos** por step (`SendTracking`):
  encolado / enviado / abierto / respondido / rebotado con
  timestamps relativos + `provider_message_id`. `SendStatusBadge`
  con 6 colores (queued gris, sent/opened lima, replied lima
  negrita, bounced/failed rojo).
- **Polling automático del detail** mientras hay sends en estado
  no terminal (queued) o sequence en IN_PROGRESS. Refetcha cada 4s;
  para cuando todo está terminal. Espejo del patrón
  `LeadStatusPoller` v0.11.1.
- **CLI `wcm outreach`** completo, espejo funcional de la UI:
  - `wcm outreach list [--lead-id N] [--status X] [--limit N]`
  - `wcm outreach show ID` — pasos + envíos.
  - `wcm outreach approve ID` — DRAFT/PAUSED → READY (409 si
    validación legal falla).
  - `wcm outreach pause ID` — READY/IN_PROGRESS → PAUSED.
  - `wcm outreach cancel ID --confirm` — irreversible.
  - `wcm outreach send ID [--step N]` — encola envío real.
  - Traducción castellana de status integrada (espejo del
    dashboard).

### Tests

- 346 pytest (+12 nuevos CLI outreach).
- 192 vitest + 3 skipped (sin cambios — el refactor mantiene
  cobertura).
- ruff + tsc + lint verde.

### Estado funcional del flujo §8 paso 6

| Capacidad | v0.12.0 | v0.12.1 |
|---|---|---|
| Aprobar refleja status en UI | ❌ "DRAFT PENDING REVIEW" se quedaba | ✅ pasa a "Lista para enviar" |
| Status badges castellano | ❌ enum en bruto | ✅ traducidos |
| Botón Enviar | ❌ no existía | ✅ con tooltip y fallback Resend |
| Vista de envíos reales | ❌ | ✅ tracking por step |
| Pausar / Cancelar / Reanudar | ❌ | ✅ botones contextuales |
| Polling automático envíos | ❌ requería F5 | ✅ cada 4s mientras inflight |
| CLI flujo completo | ❌ solo leads/campaigns | ✅ `wcm outreach …` |

---

## [0.12.0] — 2026-05-18

Sprint funcional grande sobre el dashboard ya rediseñado. Cierra 4
brechas pedidas por el operador tras E2E manual:

1. Editar correos de contacto sugeridos antes de aprobar.
2. Gestión de leads: descartar (soft) y borrar definitivo (hard).
3. CRUD de plantillas Jinja2 desde el dashboard (sin SSH).
4. Castellanización: "outreach" → "contacto comercial" en UI.

Más extras: firma legal read-only en /settings.

### Added

- **Backend `PATCH /api/v1/outreach/sequences/{id}/steps`**: edita
  los pasos de una sequence en estado editable (DRAFT_PENDING_REVIEW
  o PAUSED). Reemplaza la lista completa (semántica de PUT). Re-corre
  validación legal via helper público del composer
  (`validate_outreach_steps`) y actualiza `legal_validation_passed`.
  Si la edición rompe la validación, la sequence queda no-aprobable
  hasta corregir. AuditLog UPDATE con razones de fallo capadas a 10.
- **Backend `POST /api/v1/leads/{id}/discard`**: soft delete, status
  DISCARDED, idempotente, AuditLog UPDATE con
  `payload.action="discard"`.
- **Backend `DELETE /api/v1/leads/{id}`**: hard delete con CASCADE a
  enrichments + sequences + sends. AuditLog DELETE escrito ANTES del
  delete con snapshot (url + business_name) para evidencia
  post-borrado.
- **Backend `/api/v1/templates` CRUD completo**: GET/GET-by-id
  any_user, POST/PATCH/DELETE admin only. `name` no editable
  (renombrar rompería sequences históricas). 409 amistoso en
  IntegrityError por nombre duplicado.
- **Backend `GET /api/v1/system/firma`** (admin/operator): devuelve
  los datos legales aplicados al composer (legal_name, cif, address,
  contact_email, privacy_url, opt_out_url_base).
- **BD nuevo modelo `OutreachTemplate`** + migración Alembic 0003
  que crea la tabla y siembra `wix_intro_es` + `followup_es` con el
  contenido de los .j2 actuales hardcoded en la migración
  (reproducible aunque los .j2 desaparezcan).
- **Worker — composer refactor**: helpers públicos
  `validate_outreach_steps()` y `load_company_legal_settings()`
  exportados. `_render_template` que primero busca en BD por `name`,
  fallback a fichero `.j2` si no existe — degradación grácil.
- **Frontend `SequenceStepEditor`** Client: editor inline expandible
  con form subject + body (textarea font-mono 12 rows) + delay
  number. Botones Guardar/Cancelar. Help inline sobre mantener
  footer legal + opt_out intactos.
- **Frontend `LeadDeleteDialog`** Client: modal con confirmación
  typing-to-confirm (patrón GitHub). El operador debe tipear el
  `business_name` (o `url`) exacto para habilitar el botón rojo.
  Cierre con Escape + click fuera (deshabilitado durante pending).
- **Frontend `/settings/templates`** Server Component con
  `TemplateManager` Client. Layout master-detail simple (lista 280px
  + form/view derecha). Help expandible con variables Jinja2
  canónicas. Sin Radix Dialog (window.confirm casero para DELETE).
- **Frontend `FirmaCard`** Client read-only en `/settings` con dl
  grid 2-col denso. Warning rojo si COMPANY_CIF o COMPANY_ADDRESS
  faltan en env. Microcopy de SSH para editar.
- **CLI `wcm leads discard ID`**: soft delete CLI.
- **CLI `wcm leads delete ID --confirm`**: hard delete CLI con flag
  obligatorio (sin --confirm aborta con CliInputError antes de tocar
  API).

### Changed

- **Listado `/leads` por defecto oculta DISCARDED**
  (`WHERE status != 'discarded'`). Sigue accesible vía
  `?status=discarded` (chip futuro).
- **Rename componente `OutreachSequencePanel` → `ContactSequencePanel`**
  + test renombrado (`git mv` preserva historial). El anchor
  `#outreach` se mantiene como id técnico (no visible al usuario;
  evita romper enlaces externos).
- **Copy castellano en 6 sitios**: h3 sección "Outreach" → "Contacto
  comercial"; banner "Borrador outreach preparado" → "Borrador de
  contacto preparado"; botón "Componer outreach →" → "Componer
  contacto →"; activity feed "Outreach enviado" → "Contacto
  enviado"; empty state "Pulsa Componer outreach" → "Pulsa Componer
  contacto"; entity label "Secuencia outreach" → "Secuencia de
  contacto".

### Decisions

- **"contacto comercial" como traducción de "outreach"**: singular
  masculino, semánticamente preciso para B2B sin sonar agresivo
  (vs "captación"). URLs API y columnas BD se mantienen con
  `outreach` (estables).
- **Editar subject + body + delay, NO add/delete pasos**: 95% de
  casos cubiertos manteniendo estructura del template original.
  Menos validaciones legales que re-correr.
- **Plantillas en BD con migración + fallback a .j2**: composer
  busca en BD primero, cae al .j2 si no existe. Esto permite editar
  sin redeploy y mantiene tests del composer pasando aunque la BD
  esté vacía.
- **`name` no editable en plantillas**: renombrar rompería
  sequences históricas que la referencian por nombre. Schema PATCH
  lo excluye con `extra="forbid"`.
- **Firma legal read-only desde dashboard** (NO migrada a BD): no
  se edita con frecuencia (CIF, dirección no cambian en el día a
  día). Editar via SSH es coherente con el resto de configuración
  del sistema.
- **Borrado de leads en 2 niveles**: descartar (lima outline ámbar,
  reversible) como acción principal; borrar definitivo (rojo con
  typing-to-confirm) como acción secundaria para limpieza
  controlada o cumplimiento art. 17 RGPD.
- **PATCH steps con semántica de reemplazo (PUT-like)**: la lista
  enviada SIEMPRE es completa, no merge parcial. Evita ambigüedad
  con borrar pasos por omisión.

### Tests

- 358 pytest API (+27 nuevos: 6 outreach edit, 9 leads
  discard/delete, 12 templates CRUD).
- 22 pytest CLI (+3 nuevos: discard, delete sin confirm aborta,
  delete con --confirm).
- 191 vitest + 3 skipped React 19 (+27 nuevos: editor 8, dialog 6,
  templates manager 8, firma card 5).
- 33 Playwright ejecutables (+3 nuevos) + 62 skipped (+6 nuevos
  SSR-blocked WCM-021).
- Total: 358 + 22 = **380 pytest** · 191 vitest · 33 Playwright
  ejecutables. ruff + tsc + lint verde.

### Estado funcional del flujo §8

| Capacidad | v0.11.x | v0.12.0 |
|---|---|---|
| Editar pasos del draft antes de aprobar | ❌ | ✅ inline editor |
| Descartar leads (soft) | ❌ | ✅ botón + CLI |
| Borrar leads (hard, RGPD art.17) | ❌ | ✅ dialog typing + CLI --confirm |
| CRUD plantillas desde dashboard | ❌ filesystem .j2 | ✅ tabla BD + UI |
| Firma legal visible sin SSH | ❌ | ✅ read-only en /settings |
| UI castellano "outreach" → "contacto" | ❌ | ✅ |

---

## [0.11.1] — 2026-05-18

Hotfix de 2 bugs detectados haciendo E2E manual del flujo §8 tras
v0.11.0. Ambos son fixes de feedback al operador — el flujo
funcionaba "por debajo" pero la UI no lo reflejaba.

### Fixed

- **Sin progreso visible tras alta manual de lead** (WCM-041): el
  operador llegaba a la ficha en estado `discovered` y no había
  forma de ver el avance del pipeline (fingerprint → enrich) salvo
  hacer F5. Nuevo `LeadStatusPoller` Client llama
  `router.refresh()` cada 4s mientras `status ∈ {discovered,
  fingerprinted}`. Cuando llega a terminal (enriched, opted_out,
  etc.) el polling se detiene. Indicador visual mínimo con
  microcopy contextual ("Fingerprint en curso…" /
  "Enriquecimiento en curso…") + `role="status"` + `aria-live`.
- **"Revisar" del banner outreach llevaba a placeholder vaporware**
  (WCM-042): el `DraftBanner` enlazaba a `/leads/{id}#outreach`
  con un comentario explícito en el código "futura sección
  (cuando exista)" — la sección nunca se implementó. Misma clase
  de vaporware que "Fase 10" eliminada en v0.8.0 y "Fase 14" en
  v0.10.0. Nuevo `OutreachSequencePanel` fetcha
  `/api/v1/outreach/sequences?lead_id=N`, renderiza cada sequence
  con `SequenceCard` (status badge + template + steps con subject
  + body line-breaks preservados + delay relativo) + botón
  "Aprobar" que dispara `POST /transition action=approve`.
  Habilitado SOLO si `status=DRAFT_PENDING_REVIEW` y
  `legal_validation_passed=true`. Sección con `id="outreach"` +
  `scroll-mt-12` para que el anchor del banner funcione.
- **`GET /outreach/sequences` 500 con sequences legacy** (descubierto
  al implementar el panel): el schema `OutreachStep` con
  `extra="forbid"` rechazaba sequences viejas persistidas con
  shape `body/subject/template/delay_days` (sin `step_index` ni
  `delay_days_from_previous`). El endpoint devolvía 500 al
  intentar serializarlas. Schema ahora tolera shapes legacy con
  `extra="allow"`, `step_index` con default 0, y
  `AliasChoices("delay_days_from_previous", "delay_days")`. Los
  composers nuevos siguen escribiendo solo el shape canónico —
  el cambio es de tolerancia en lectura.

### Tests

- 280 pytest API (sin cambios, suite sigue verde — schema más
  permisivo no rompió validaciones existentes).
- 164 vitest + 3 skipped React 19 (+16 nuevos: LeadStatusPoller 6
  con fake timers, OutreachSequencePanel 10).
- ruff + tsc + lint verde.

### Estado funcional del flujo de prospección §8

| Paso | v0.11.0 | v0.11.1 |
|---|---|---|
| 1-4 (alta + fingerprint + enrich) | ✅ funcionan | ✅ **+ feedback visible al operador** |
| 5 (composer prepara borrador) | ✅ | ✅ |
| 6 (operador revisa/aprueba) | ❌ "Revisar" vaporware | ✅ **panel real con botón Aprobar** |

---

## [0.11.0] — 2026-05-18

Primer sprint de **ampliación funcional** sobre el dashboard ya rediseñado.
Añade **alta manual de leads** (single + bulk) en dashboard y CLI. Cierra
brecha funcional detectada al hacer E2E manuales: hasta ahora los leads
solo podían entrar al sistema vía campaña de Google Places.

### Added

- **`POST /api/v1/leads`** (201, operator/admin): alta manual de un lead
  con URL + metadata opcional (business_name, sector, region, country).
  `pg_insert.on_conflict_do_nothing` + 409 con `details.existing_lead_id`
  si la URL ya existe. AuditLog DISCOVER con `legal_ground="6.1.f"`
  (misma base RGPD que la prospección automática — no cambia por
  procedencia) y `payload.source="manual_single"`. Fire-and-forget
  `enqueue_lead_fingerprint` + `enqueue_lead_enrich` tras commit — si
  Celery cae, lead persiste y warning en log; operador puede disparar
  manual desde la ficha.
- **`POST /api/v1/leads/bulk`** (200, rate-limit 10/min): alta masiva
  hasta 200 URLs. NO aborta batch ante fallos aislados — cada URL es
  transaccionalmente independiente vía INSERT ON CONFLICT. Devuelve
  `LeadBulkCreateResult` con listas separadas `created` (LeadRead
  completos), `skipped_duplicates` (con `lead_id` del existente),
  `failed` (con `reason`). `payload.source="manual_bulk"` +
  `batch_size`.
- **`packages/scraper-core/src/wcm_scraper_core/urls.py`** con
  `normalize_lead_url(url)` extraído del ProspectorAgent. Single
  source of truth para canonicalización entre alta manual y crawler:
  strippea querystring (UTMs, fbclid, gclid), fragment, `www.`,
  trailing slash. Evita duplicados accidentales.
- **`/leads/new`**: Server Component con header castellano "Nuevo
  lead" + microcopy explicativa + form + microcopy legal RGPD abajo
  (`legal_ground=6.1.f` + procedencia en `payload.source`). Fetch
  `/leads?limit=200` para alimentar datalists de sector/región
  (top 20 por frecuencia).
- **`LeadCreateForm`** con tabs ARIA single/bulk (`useState`, no
  searchParams):
  - **SingleTab**: réplica del patrón `LaunchCampaignForm`. Submit
    201 → toast + `router.push("/leads?selected=N")`. Submit 409 →
    toast.error + botón secundario "Abrir lead existente #N" que
    navega al lead que duplicaba.
  - **BulkTab**: textarea `font-mono` 12 rows + `BulkPreview`
    debounced con counts (lima/ámbar), lista expandible de
    inválidas con número de línea. Submit envía solo las URLs
    válidas detectadas por el preview. Toast resumen
    `${created} · ${skipped} · ${failed}` (warning si created===0).
    Si hay fallos, toast extra con razones (primeras 3). 429 con
    copy específico.
  - **`parseBulkUrls`** puro testable: 1 URL por línea, ignora vacías
    y comments `#`. Autoañade `https://` si falta protocolo. Rechaza
    espacios explícitamente (Chromium los toleraba con %20), rechaza
    hosts sin TLD (`localhost`, `foo`), rechaza protocolos distintos
    a http/https.
- **Botón "+ Nuevo lead"** outline ghost en cabecera de `/leads`
  junto al lima primario "+ Lanzar campaña". Jerarquía visual clara:
  lima = acción frecuente (campaña), outline = alternativa menos
  común (alta manual).
- **`wcm leads create` CLI** con XOR `--url`/`--bulk-file`. Bulk lee
  1 URL por línea, ignora vacías y comments. 409 muestra mensaje
  específico con `existing_lead_id` (no el genérico "API HTTP 409").
  Bulk imprime resumen `N creados · M duplicados · K fallos` + razones
  de los primeros 3 fallos.

### Changed

- **`apps/worker/src/wcm_worker/agents/prospector.py`**: `_normalize_url`
  local sustituido por import de `wcm_scraper_core.urls.normalize_lead_url`
  para compartir lógica con el endpoint manual. Test
  `test_prospector.py` adaptado al nuevo import.
- **`CliApiError`** acepta opcionalmente `details: dict` que recibe
  desde `_raise_from_response` el campo `error.details` del envelope
  del API. Permite a comandos reaccionar a casos específicos sin
  parsear el message (caso `existing_lead_id` en 409 single).

### Decisions

- **`legal_ground="6.1.f"` para alta manual** (NO `"manual_operator"`):
  el art. 6.1.f cubre prospección B2B sistemática + datos públicos
  bajo interés legítimo; la base RGPD NO cambia porque la procedencia
  sea manual u automática. La procedencia va en `payload.source`
  (`manual_single` / `manual_bulk` / `prospector_campaign`).
  Semánticamente correcto y consistente con el resto del audit.
- **`normalize_lead_url` strippea querystring por defecto**: evita
  duplicados accidentales por UTMs (`utm_source`, `fbclid`, `gclid`).
  Las URLs comerciales objetivo casi nunca dependen de querystring.
  Documentado en docstring del helper.
- **Fire-and-forget en vez de `celery.chain`**: la simplicidad de dos
  `send_task` independientes basta — el enricher lee el lead fresh
  de la DB y no depende del fingerprinter (campos distintos). Si
  surge problema de ordering en producción, promover a chain.
- **Tabs con `useState`, no searchParams**: evita un SSR roundtrip
  al cambiar de tab y mantiene el formulario rellenado localmente.
- **Bulk NO aborta el batch ante fallos aislados**: cada URL es
  transaccionalmente independiente vía INSERT ON CONFLICT. El
  operador prefiere "3 de 5 ok" a "0 de 5 por culpa de la 4ª".
- **Rechazo explícito de espacios en `parseBulkUrls`**: Chromium
  los tolera codificándolos como %20, lo cual NO es lo que un
  operador quiere si pegó accidentalmente una línea descriptiva.
- **CLI `--url` XOR `--bulk-file`**: validación en el comando con
  `CliInputError` antes de tocar el API. Coherente con typer y
  prevenir errores 4xx ruidosos.

### Tests

- 280 pytest API (+11 nuevos: alta single/bulk con audit, normalize
  URL vía SQL compilado, 409 con existing_lead_id, 422 URL
  malformada, Celery KO sigue devolviendo 201, bulk mixed outcomes,
  bulk RBAC, bulk empty/oversize 422, audit legal_ground+source+batch_size).
- 19 pytest CLI (+8 nuevos: single éxito, single 409 exits 1, XOR
  validation ambos sentidos, bulk parsea comments/vacías, bulk
  summary con razones, bulk file vacío error, bulk file no
  existe error).
- 148 vitest + 3 skipped React 19 (+15 nuevos: parseBulkUrls 8
  cases, BulkPreview 3, LeadCreateForm tabs 4).
- 30 Playwright ejecutables (+7 nuevos) + 56 skipped (+1
  SSR-blocked WCM-021).
- ruff + tsc + `pnpm lint` verde.

### Estado funcional del flujo de prospección §8

| Paso | Antes v0.11.0 | Después v0.11.0 |
|---|---|---|
| 1. Lanzar campaña | ✅ | ✅ |
| 2. Prospector (Google Places) | ✅ | ✅ |
| 3. Fingerprinter | ✅ | ✅ |
| 4. Enricher | ✅ | ✅ |
| 5. Outreach composer | ✅ | ✅ |
| 6. Revisar/aprobar outreach | ✅ | ✅ |
| **Alta manual de URLs concretas** | ❌ bloqueado | ✅ **single + bulk** |

---

## [0.10.0] — 2026-05-18

Rediseño de **`/settings`** — última pantalla del dashboard. **Cierre
del ciclo completo del rediseño visual**: 11/11 pantallas operativas
bajo el nuevo lenguaje. Última release del trayecto iniciado en v0.4.0.

Pantalla distinta del resto: informativa, no listado. Confirmó la
variación del patrón ADR-036 para pantallas no-list, hoy documentada
explícitamente.

### Added

- **Endpoint `GET /api/v1/system/info`** (admin/operator) con 6 campos
  de runtime: `version` (de pyproject.toml vía
  `importlib.metadata.version`), `environment` (de ApiSettings),
  `python_version`, `alembic_revision` (de `SELECT version_num FROM
  alembic_version`), `uptime_seconds` (desde `_PROCESS_STARTED_AT`
  módulo-level capturado al import), `health` summary 4 campos
  (overall + db + redis + r2). Reúsa `_check_db/_check_redis/_check_r2`
  de `/health/deep` para single source of truth sobre qué consideramos
  sano. Mismo criterio overall: db/redis críticos → fail; r2 opcional
  → degraded. 6 tests unit cubriendo shape canónica, alembic null
  cuando la tabla no existe (BD sin migrar), overall degraded por r2,
  overall fail por db, viewer 403, sin auth 401.
- **3 componentes presentacionales** en
  `apps/dashboard/src/app/(app)/settings/_components/`:
  - `UserCard` — dl grid 2-col denso con 6 filas (email, nombre, rol
    con `RoleBadge` lima para admin, activo, alta, id). Error
    explicativo cuando `/auth/me` falla.
  - `SystemInfoPanel` — 5 filas runtime + sub-bloque health con
    `OverallBadge` (ok/degraded/fail por color) y 3 `HealthRow` con
    dot coloreado. `EnvBadge` ámbar para "production" como
    recordatorio visual. `formatUptime` escalable (s → m → h+m →
    d+h+m). Error explicativo con sugerencia de `systemctl status
    webcafeina-api` cuando el API no responde.
  - `OperationRunbook` — runbook condensado con 2 secciones (editar
    `.env` vía SSH + systemctl restart, gestión usuarios vía CLI
    `wcm users`). Sustituye los 2 placeholders previos por
    información accionable. Explícito sobre "no hay UI prevista"
    para usuarios (sin promesas vaporware).
- **Spec Playwright** `tests/e2e/settings-redesign.spec.ts` con 7
  tests. 4 pasan client-side (header castellano "Ajustes", 3
  secciones, guardia "Fase 14 NO presente", OperationRunbook con SSH
  y comandos CLI); 3 marcados `test.skip(SSR_BLOCKED, "WCM-021")`
  para datos server-fetched. Fixture base ampliado con handler de
  `/api/v1/system/info`.

### Changed

- **`/settings/page.tsx`**: refactor completo de 3 Cards de shadcn
  genéricas a layout 2-col denso (1fr Usuario+Sistema | 360px
  Operación) con responsive a 1-col. Fetch en paralelo de `/auth/me`
  + `/system/info` con `.catch()` defensivo — cualquier dependencia
  caída se refleja en su componente sin romper la página entera.
- **Título "Settings" → "Ajustes"** — el inglés violaba CLAUDE.md §3
  (castellano de España primario) y además era inconsistente con el
  nav lateral que ya ponía "Ajustes".
- **`apps/dashboard/README.md`** — tabla de páginas actualizada con
  las descripciones reales tras los rediseños v0.4.0..v0.10.0;
  incluía aún una mención "Fase 10" desfasada en
  `/projects/[id]/diff` que se actualizó por la copy honesta de
  v0.8.0.

### Fixed

- **Bug P0 — Mentira "UI de gestión: Fase 14"**: el placeholder
  original prometía "UI de gestión llega en Fase 14". Fase 14 pasó
  hace meses; no hay UI de gestión planificada y el equipo (9
  personas) no la justifica. Sustituido por explicación honesta del
  flujo CLI `wcm users`. Misma clase de mentira que la "Fase 10" del
  diff que se eliminó en v0.8.0 con WCM-034. Guardia automática
  añadida en spec Playwright para prevenir regresiones.

### Decisions

- **Variación del patrón ADR-036 para pantallas no-list**
  (documentada): el bloque 1 sigue siendo un endpoint backend
  dedicado pero con runtime info en vez de counts; el bloque 4 omite
  FilterChips y 2 empty states (no aplica filtrar lo que no es
  lista); resto idéntico (componentes presentacionales, refactor
  page denso, spec). Esta variación se anticipó al revisar
  `/settings` y se documentó tras aplicarla — el patrón es robusto.
- **`/system/info` admin/operator (no any_user)**: la revision de
  Alembic y los component paths pueden filtrar arquitectura interna.
  Viewers ven solo lo que les sirve para operar (leads, projects,
  campaigns), no detalles del runtime del servidor.
- **`_PROCESS_STARTED_AT` módulo-level (no persistente)**: cada
  `systemctl restart webcafeina-api` resetea el uptime. Eso es lo
  que el operador quiere ver — el uptime real del proceso que está
  sirviendo la request, no el uptime acumulado de la máquina.
- **`alembic_revision` por SELECT a la BD (no por `ScriptDirectory`
  del repo)**: refleja qué migration está APLICADA en la BD, no qué
  HEAD tiene el repo. Lo que el operador necesita saber.
- **Reúso de `_check_*` de health.py**: importar `_check_db`,
  `_check_redis`, `_check_r2` (privados con `_`) tiene el coste de
  cruzar la barrera de privacy del módulo, pero el beneficio es una
  única fuente de verdad sobre qué consideramos sano. Más limpio que
  duplicar lógica.

### Tests

- 475 pytest (+6 nuevos: shape, alembic null, degraded r2, fail db,
  viewer 403, sin auth 401).
- 133 vitest + 3 skipped React 19 (+13 nuevos: UserCard render +
  rol admin lima + error null; SystemInfoPanel render + 4 escalas
  uptime + env production ámbar + alembic null copy + 3 health
  rows + overall fail/degraded + error null; OperationRunbook 2
  secciones + comandos + guardia "Fase 14 NO presente" + guardia
  "no promete vaporware").
- 23 Playwright ejecutables (+4 nuevos — más de los 2 habituales
  porque el runbook y la guardia "Fase 14" son client-side puros) +
  55 skipped (+3 nuevos, todos SSR-blocked por WCM-021).

### Estado del rediseño visual — ✅ CICLO CERRADO

| Pantalla | Estado |
|---|---|
| `/login` | fuera de scope (app group `(auth)`) |
| `/` Panel | ✅ v0.5.0 |
| `/campaigns` | ✅ v0.6.0 + v0.6.1 |
| `/leads` master-detail | ✅ v0.4.0 |
| `/leads/[id]` full-page | ✅ v0.6.0 |
| `/projects` | ✅ v0.7.0 |
| `/projects/[id]` + `/checklist` + `/diff` | ✅ v0.8.0 |
| `/errors` | ✅ v0.9.0 |
| `/residual-tasks` | ✅ v0.9.0 |
| `/settings` | ✅ **v0.10.0** |

**11 / 11 pantallas operativas** del dashboard bajo el nuevo lenguaje
visual. Ciclo iniciado con `/leads` (v0.4.0, 2026-05-16) y cerrado
con `/settings` (v0.10.0, 2026-05-18) — 6 sprints, 4 días calendario.

---

## [0.9.0] — 2026-05-18

Rediseño simultáneo de `/errors` + `/residual-tasks` — primer sprint
del rediseño visual que mete 2 pantallas en una sola release porque
ambas comparten patrón exacto (lista plana + filtro por enum, sin
master-detail). Cierra el rediseño de todas las pantallas operativas
del dashboard salvo `/settings`.

### Added

- **Endpoint `GET /api/v1/errors/stats`** (rol admin/operator — datos
  de runtime potencialmente sensibles). 8 buckets en ventana
  configurable `since_hours` (default 168h ≡ 7 días, max 90×24): total,
  counts por `ErrorSeverity` (critical, error, warning, info, debug),
  `distinct_components`, `last_critical_at`. Implementación con 8
  `session.execute` y `Pydantic Query(le=24*90)` para validar la
  ventana. 5 tests unit cubriendo shape canónica, null cuando no hay
  críticos, viewer 403, sin auth 401, ventana inválida 422.
- **Endpoint `GET /api/v1/residual-tasks/stats`** (rol any_user — toda
  la operación necesita visibilidad de carga pendiente). 9 buckets:
  total + 5 counts por status + `blocking_go_live` + `distinct_projects`
  + `estimated_minutes_pending` (suma de `estimated_minutes` excluyendo
  DONE/SKIPPED vía `notin_()`). 4 tests unit con verificación del SQL
  compilado (`literal_binds`) confirmando `NOT IN (done, skipped)`.
- **`ErrorsTable`** en `apps/dashboard/src/app/(app)/errors/_components/`
  — tabla con 5 columnas (Cuándo · Severidad · Componente · Mensaje ·
  Proyecto), `SeverityBadge` con 5 colores diferenciados (critical
  fondo rojo + font-semibold, error texto rojo, warning ámbar, info
  gris, debug muted), responsive `hideUntil="md"` en Componente +
  Proyecto, link tabular-nums a `/projects/{id}` cuando aplica.
- **`ResidualTasksTable`** en
  `apps/dashboard/src/app/(app)/residual-tasks/_components/` — tabla
  con 7 columnas (Proyecto link · Categoría con badge ámbar para
  `blocking_go_live` · Tarea · Asignar · Min · Estado pill castellano ·
  Acción). Reúsa `MarkDoneButton` existente solo en filas no
  done/skipped (cerradas no tienen acción pendiente).
- **Spec Playwright** `tests/e2e/errors-residuals-redesign.spec.ts` con
  12 tests (6 por pantalla). 2 pasan client-side (headers y subtítulos
  castellanos visibles); 10 marcados `test.skip(SSR_BLOCKED,
  "WCM-021")` para KPIs, counts en chips, empty con datos, URL tras
  click. Fixture base ampliado con handlers específicos `/errors/stats`
  y `/residual-tasks/stats` que devuelven el objeto agregado (los
  catch-all previos devolvían `[]` y rompían el shape).

### Changed

- **`/errors/page.tsx`**: refactor a Server Component que fetcha
  `/errors` + `/errors/stats` en paralelo con `.catch()` defensivo.
  Header descriptivo + `KpiStrip` con 6 KPIs (Total 7d · Críticos ·
  Errores · Warnings · Componentes · Último crítico relativo) +
  `FilterChips` por severity con counts del backend (solo se renderiza
  si `stats.total > 0`). Empty state con 2 ramas: `systemEmpty` lima
  "Sistema estable" con mención de Sentry y `journald` como segundo
  lugar de búsqueda, vs filtro neutro.
- **`/residual-tasks/page.tsx`**: refactor análogo con `KpiStrip` de 5
  KPIs (Total · Abiertas agregado [open+in_progress+blocked] ·
  Bloqueantes ámbar · Proyectos · Tiempo pendiente formateado "Nh Mm")
  + `FilterChips` por status. Empty state explica el rol del agente
  `checklist-generator` (mover DNS, configurar Stripe, etc.) cuando el
  operador no entiende por qué la lista está vacía.

### Decisions

- **Agrupación de 2 pantallas en una release** (extensión a ADR-036):
  cuando 2 pantallas comparten patrón exacto (lista plana + filtro por
  enum, sin master-detail ni subpáginas), pueden meterse en la misma
  release con un commit por bloque que toca ambas a la vez. Reduce
  overhead de release sin sacrificar granularidad. NO aplicable cuando
  las pantallas tienen schemas o componentes claramente distintos.
- **`Abiertas` agregado en KpiStrip de residual-tasks**: muestro
  `open + in_progress + blocked` como un único KPI porque el operador
  piensa "abiertas vs cerradas" — los 3 sub-estados son ruido a nivel
  global. El detalle por status sigue en `FilterChips` para quien lo
  necesita.
- **`/errors/stats` con `since_hours` configurable, default 168h
  (7 días)**: 7 días es el horizonte natural de un on-call humano.
  Configurable por si el operador quiere ventana corta tras un
  incidente o larga para detectar drift.
- **`/errors/stats` solo admin/operator**: los errores incluyen stack
  traces y component paths que pueden filtrar arquitectura interna.
  Viewers no necesitan esa visibilidad.

### Tests

- 469 pytest (+9 nuevos: 5 errors-stats + 4 residual-tasks-stats).
  Total ruff + tsc + `pnpm lint` verde.
- 120 vitest + 3 skipped React 19 (+11 nuevos: ErrorsTable + 
  ResidualTasksTable cubriendo render, 5 severities, 5 status pills,
  link a proyecto, MarkDoneButton condicional, empty).
- 19 Playwright ejecutables (+2 nuevos) + 52 skipped (+10 nuevos,
  todos SSR-blocked por WCM-021).

### Estado del rediseño visual

| Pantalla | Estado |
|---|---|
| `/login` | original |
| `/` Panel | ✅ v0.5.0 |
| `/campaigns` | ✅ v0.6.0 + v0.6.1 |
| `/leads` master-detail | ✅ v0.4.0 |
| `/leads/[id]` full-page | ✅ v0.6.0 |
| `/projects` | ✅ v0.7.0 |
| `/projects/[id]` + `/checklist` + `/diff` | ✅ v0.8.0 |
| `/errors` | ✅ **v0.9.0** |
| `/residual-tasks` | ✅ **v0.9.0** |
| `/settings` | original (modelo a replicar) |

**9 pantallas** rediseñadas. Solo `/settings` queda para cerrar el
rediseño visual completo del dashboard.

---

## [0.8.0] — 2026-05-18

Rediseño de `/projects/[id]` + sus 3 sub-páginas (`overview`,
`checklist`, `diff`) — la pantalla más grande del lote pendiente, con
4 rutas anidadas que ahora comparten un `ProjectHeader` único. Quinta
release del rediseño visual, siguiendo el patrón consolidado en
ADR-036.

### Added

- **Endpoint `GET /api/v1/projects/{id}/summary`** (rol any_user)
  para evitar 3-4 fetches por sub-página. Devuelve agregados clave:
  `lead_origin` reducido (id, business_name, score,
  builder_detected); counts de fases por status
  (`phases_total/completed/failed/running/pending`);
  `current_phase_name` (la RUNNING si la hay, sino la última
  COMPLETED por `completed_at` DESC); counts de residual-tasks
  (`residual_total/open/done`, donde `open = total - done - skipped`).
  Implementación: 2 `session.get` + 3 `session.execute` con
  `GROUP BY`. 8 tests unit cubriendo proyecto sin fases, lead
  borrado defensivo, current_phase RUNNING > COMPLETED, residual_open
  excluye DONE/SKIPPED, 404, 401.
- **4 componentes shared** en
  `apps/dashboard/src/app/(app)/projects/[id]/_components/`:
  - `ProjectHeader` (presentacional) — header común a las 4
    sub-páginas: breadcrumb `← Proyectos`, badge `Proyecto · #N`,
    título cliente, URL origen externa, `PhaseProgressBar`, MetaLine
    densa (fase actual · residuales · lead origen con score), slot
    opcional `actions` (para `ProjectActions` existente), tabs.
  - `ProjectTabs` (Client, `usePathname`) — 3 tabs Overview ·
    Checklist · Visual diff con active state por pathname exacto.
    Badge condicional con count de residuales abiertas en
    Checklist (solo si > 0; colores diferenciados según tab
    activo/inactivo).
  - `PhaseProgressBar` (presentacional) — barra multi-segmento con
    4 colores: completadas (lima sólido), fallidas (rojo), running
    (lima con `animate-pulse`), pendientes (gris). Cifra `N/M`
    tabular a la derecha.
  - `ProjectPhasesTimeline` (presentacional) — timeline vertical con
    icono por status (`CheckCircle2/Loader2/AlertCircle/MinusCircle/
    Circle` de lucide-react), badge "intento N" cuando `attempt > 1`,
    `error_log` con `line-clamp-2` si existe, columna derecha con
    when relativo + duración formateada. Empty state contextual
    cuando 0 fases ("Pulsa Start para encolar el pipeline").
- **Spec Playwright** `tests/e2e/projects-detail-redesign.spec.ts`
  con 14 tests en 3 describes (overview · checklist · diff). Todas
  marcadas `test.skip(SSR_BLOCKED, "WCM-021")` — la página depende
  100% del fetch del Server Component (sin proyecto cargado no hay
  nada que el browser pueda verificar). La cobertura real vive en
  los 17 vitest de componentes hasta que MSW esté.

### Changed

- **`/projects/[id]/page.tsx`** (overview): refactor de 174 líneas
  con 4 Cards apiladas a layout 2-col en lg+ (timeline 1fr +
  `ConfigPanel` 280px sidebar). En estrecho colapsa a 1 col.
  `ConfigPanel`: grid kv compacto con 6 filas sustituyendo Card
  "Configuración" + Card "Estado" del original (los datos de
  estado ya viven en el header denso). Fetch en paralelo
  project + summary + phases.
- **`/projects/[id]/checklist/page.tsx`**: refactor de tarjetas
  anidadas a sections con header de categoría + `<ul divide>`.
  Mantiene el orden canónico (`blocking_go_live` → `client_config`
  → `visual_content` → `post_go_live` → `other`), pero
  `blocking_go_live` ahora con borde ámbar warning (urgencia
  visual). `TaskStatusPill` con 5 status en castellano.
- **`/projects/[id]/diff/page.tsx`**: placeholder actualizado.
  Elimina la mentira "se implementa en Fase 10" del copy original
  (Fase 10 pasó hace meses; el bloqueo es UI, no backend). Nuevo
  copy reconoce que `packages/visual-diff/` ya existe y explica
  los 4 pasos del flujo + callout informativo apuntando a la
  columna Diff del listado para ver el score agregado mientras
  tanto. Score medio del proyecto visible en la cabecera.

### Fixed

- **Campo schema `error_log`** (no `error_message`): asumí mal en
  `ProjectPhasesTimeline`. Corregido tras descubrir en preflight
  tsc — el schema canónico (`ProjectPhaseRead`) usa `error_log:
  string | null`.
- **`has_ecommerce` / `preserve_paths` como `boolean | undefined`**:
  pydantic2ts serializa defaults como opcionales. `?? false`
  defensivo en `ConfigPanel`.

### Decisions

- **`residual_open = total - done - skipped`**: IN_PROGRESS y
  BLOCKED cuentan como "abiertos" porque siguen requiriendo acción
  humana. Decisión semántica del producto, documentada en
  docstring del endpoint.
- **`current_phase_name` fallback a última COMPLETED**: si no hay
  fase RUNNING, mostramos la última terminada como contexto. Más
  útil que None puro.
- **`blocking_go_live` con borde ámbar warning**: urgencia visual
  sin ser alarmante. Las demás categorías con border neutro.
- **14 specs Playwright skipped sin tests ejecutables nuevos**: el
  detalle del proyecto depende 100% del fetch SSR — no hay nada
  client-side puro que testear sin proyecto. Honesto. Pasarán
  cuando WCM-021 esté.

### Tests

- 461 pytest (+8 projects/{id}/summary).
- 109 vitest + 3 skipped React 19 (+17 nuevos: PhaseProgressBar,
  ProjectTabs, ProjectHeader, ProjectPhasesTimeline).
- 17 Playwright ejecutables (sin cambios) + 42 skipped (+14 nuevos
  del detalle, todos SSR-blocked).
- ruff + tsc + `pnpm lint` verde. Cleanup preventivo de
  `.next/types/* [N]*.ts` duplicados por iCloud (WCM-038) antes del
  preflight de tsc.

### Estado del rediseño visual

| Pantalla | Estado |
|---|---|
| `/login` | original |
| `/` Panel | ✅ v0.5.0 |
| `/campaigns` | ✅ v0.6.0 + v0.6.1 |
| `/leads` master-detail | ✅ v0.4.0 |
| `/leads/[id]` full-page | ✅ v0.6.0 |
| `/projects` | ✅ v0.7.0 |
| `/projects/[id]` + `/checklist` + `/diff` | ✅ **v0.8.0** |
| `/errors`, `/residual-tasks` | original (WCM-035, siguiente) |
| `/settings` | modelo a replicar |

**5 pantallas + 2 sub** rediseñadas. Quedan solo **2 pantallas**
para tener el dashboard completo bajo el nuevo lenguaje.

---

## [0.7.0] — 2026-05-18

Rediseño del **listado de proyectos** (`/projects`), cuarta pantalla
del flujo de uso (tras `/`, `/leads`, `/campaigns`). Mismo patrón
consolidado de 5 bloques granulares: endpoint stats + componentes
presentacionales + refactor page + pulido + tests.

Esta release consolida también un **patrón compartido** que se está
afianzando: `KpiStrip` y `FilterChips` ahora viven en
`apps/dashboard/src/components/` y los usan 2+ páginas.

### Added

- **Endpoint `GET /api/v1/projects/stats`** (rol any_user) análogo a
  `/leads/stats`. 8 campos: `total`, `queued`, `running`, `blocked`
  (= `blocked_human_input`), `completed`, `failed_or_cancelled`
  (agregado `qa_failed` + `cancelled`), `distinct_builders` (excluye
  null/UNKNOWN), `avg_visual_diff_score` (decimal 0..1, null si
  ningún proyecto tiene diff). 8 ejecuciones SQL separadas. 5 tests
  unit.
- **`ProjectsTable`** en
  `apps/dashboard/src/app/(app)/projects/_components/` — tabla con 7
  columnas ordenadas por importancia operativa: cliente (con link a
  /projects/{id} + meta a lead origen), origen, builder, destino,
  estado, diff con barra mini coloreada por umbral
  (≥85 verde / 70-84 ámbar / <70 rojo; umbral 0.85 del §13
  CLAUDE.md), actividad relativa. Responsive con `hideUntil="md"/"lg"`
  (mismo patrón que CampaignRunsTable). 18 tests Vitest.
- **Empty states diferenciados**:
  - `EmptyProjects` (sistema sin proyectos): card lima con onboarding
    "Convierte un lead cualificado en migración" + descripción del
    pipeline + 2 CTAs (Ir a leads + Ver actividad del Panel).
  - `EmptyFilterResult` (proyectos existen pero filtro deja 0): card
    neutra "Sin proyectos en estado X. Quita el filtro o lanza uno
    nuevo desde un lead". Más discreto — no es estado inicial, es
    resultado de búsqueda.
- **Filtros chips por status** con URL state `?status=running`. 5
  chips (encolados / en curso / bloqueados / completados / cancelados)
  reutilizando `FilterChips`. Counts tomados de `/projects/stats`
  (globales, no del listado filtrado). Chips ocultos cuando
  `stats.total === 0`.
- **Spec Playwright** `tests/e2e/projects-redesign.spec.ts` con 7
  tests (2 ejecutables + 5 SSR-blocked).

### Changed

- **`OverviewKpiStrip` → `KpiStrip`** movido a
  `apps/dashboard/src/components/kpi-strip.tsx`. Genérico desde el día
  1, solo el nombre lo ligaba al Overview. Mismo patrón que el `git
  mv` de `FilterChips` en v0.5.0. Ahora 2 páginas lo usan
  (`/` y `/projects`); el patrón "componente promovido a shared
  cuando lo usan 2+ páginas" queda consolidado.
- **`apps/dashboard/src/app/(app)/projects/page.tsx`** refactorizado
  de tabla shadcn genérica con 7 columnas a layout consistente con el
  resto del rediseño: header + KpiStrip + sección listado con chips
  + tabla densa o empty state contextual.

### Decisions

- **`failed_or_cancelled` agregado en stats** (2 estados en 1
  bucket) — ambos son terminales "no exitosos" y al operador le
  interesan juntos. El chip de filtro correspondiente filtra solo
  por `cancelled` (más frecuente); si en futuro hace falta
  distinguir, se desdobla.
- **`blocked` = solo `blocked_human_input`** en stats. Es el único
  estado bloqueado real que requiere acción humana. Color ámbar
  warning para destacar.
- **Acción primaria "+ Nuevo proyecto" linkea a /leads** (no a un
  form de creación). Los proyectos nacen siempre de un lead
  cualificado — el modelo mental se refuerza desde el botón. El
  tooltip lo explica explícitamente.
- **Counts de filtros desde stats globales**, no del listado
  filtrado — el operador ve cuántos hay en cada estado antes de
  pulsar.
- **DiffIndicator con umbral 85/70**: 0.85 viene del §13 CLAUDE.md
  (criterio de éxito MVP del visual diff). Verde ≥85, ámbar 70-84,
  rojo <70, "—" si null.

### Tests

- 453 pytest (+5 projects/stats endpoint).
- 92 vitest (+18 ProjectsTable, 3 skipped React 19 desde v0.6.0
  intactos).
- 17 Playwright ejecutables (+2 nuevos projects) + 28 skipped
  (23 antiguos + 5 nuevos projects).
- ruff + tsc + `pnpm lint` verde (preflight completo aplicado tras la
  lección de v0.6.0 → v0.6.1; lint añadido a la memoria persistente
  del proyecto).

### Estado del rediseño visual

| Pantalla | Estado |
|---|---|
| `/login` | original |
| `/` Panel | ✅ v0.5.0 |
| `/campaigns` | ✅ v0.6.0 + v0.6.1 |
| `/leads` master-detail | ✅ v0.4.0 |
| `/leads/[id]` full-page | ✅ v0.6.0 |
| `/projects` | ✅ **v0.7.0** |
| `/projects/[id]` + sub | original (siguiente) |
| `/errors`, `/residual-tasks` | original |
| `/settings` | modelo a replicar |

**4 pantallas rediseñadas en producción** de 11 + 3 sub. Pendientes:
detalle de proyecto + sub-páginas (checklist, diff), errores y
residual-tasks.

---

## [0.6.1] — 2026-05-18

Hotfix de CI: el `EmptyHistorico` de `/campaigns` introducido en v0.6.0
usaba 2 `<a href="/leads">` / `<a href="/">` para enlaces internos. La
regla ESLint `@next/next/no-html-link-for-pages` falló en CI matrix
(Node 20 + 22) — pedía `<Link>` de next/link.

### Fixed

- `apps/dashboard/src/app/(app)/campaigns/page.tsx`: 2 `<a>` →
  `<Link>` en el empty state del histórico. Comportamiento idéntico
  para el operador; ganamos prefetch automático y evitamos full
  reload entre rutas.

Tests/lint: tsc + vitest 77 + `pnpm lint` verdes en local. CI debería
quedar verde tras el push de este tag.

---

## [0.6.0] — 2026-05-18

Consolidación del **flujo de prospección end-to-end**. Cierra dos
piezas pendientes del rediseño visual:

- **`/leads/[id]` full-page** reusa el `LeadDetailPane` del
  master-detail (`/leads?selected=N`) — coherencia 100% entre los dos
  modos del producto, eliminando la duplicación visual previa.
- **`/campaigns`** rediseñado completo con layout 3-zona: lanzar →
  en curso → histórico. Bug P0 de copy obsoleto eliminado.

Patrón consistente con v0.4.0 (/leads) y v0.5.0 (/): endpoint dedicado
+ componentes presentacionales reutilizables + refactor de la página +
pulido responsive + capa de tests. 5 commits granulares por rediseño.

### Added

- **Endpoint `GET /api/v1/campaigns/runs`** (rol any_user) para el
  histórico de campañas. Hasta ahora solo había `/runs/{task_id}`
  (detalle de UNA). Filtros: `status` (CampaignStatus enum:
  queued|running|completed|failed|cancelled), `since` (ISO datetime),
  `limit` (1..100, default 20), `offset`. Ventana por defecto 30
  días. Ordenado por `started_at` DESC. Schema `CampaignRunSummary`
  con campos derivados: `duration_s` calculado (null si aún corre),
  `leads_count` = `len(created_lead_ids)`, `warnings_count` =
  `len(warnings)` (para badge sin payload pesado). 9 tests unit con
  inspección del SQL compilado (`literal_binds`).
- **3 componentes nuevos** en
  `apps/dashboard/src/app/(app)/campaigns/_components/`:
  - `CampaignRunsTable` — tabla histórica con 6 columnas (lanzada,
    sector·región, producidos/objetivo con barra mini, duración
    compacta, status badge en castellano, indicadores warnings/error).
    Responsive: oculta columnas secundarias en viewports estrechos via
    prop `hideUntil="md" | "lg"`.
  - `CampaignProgressCard` (Client, polling 5s) — visible solo cuando
    hay campañas QUEUED/RUNNING. Cada activa: barra de progreso
    animada `lead_count/target_count` + sector·región + tiempo elapsed
    + status badge. Auto-oculta cuando 0 activas.
  - `LaunchCampaignForm` refactorizado a layout horizontal compacto
    (sector flex-1 | región flex-1 | objetivo w-24 | botón). Nueva
    prop `sectorSuggestions` y `regionSuggestions` para `<datalist>`
    autocompletado.
- **Spec Playwright** `tests/e2e/campaigns-redesign.spec.ts` con 9
  tests (6 ejecutables + 3 SSR-blocked). Incluye test del fix P0
  que verifica que la nota obsoleta NO aparece.

### Changed

- **`/leads/[id]` full-page** simplificada de 158 líneas a 50 líneas.
  Server Component que fetcha el lead + renderiza `LeadDetailPane`
  (el mismo del master-detail) envuelto en layout edge-to-edge con
  breadcrumb arriba ("← Lista de leads" + "Abrir en master-detail").
  Eliminado `refingerprint-button.tsx` local — `LeadActions` ya cubre
  re-fingerprint + componer outreach + opt-out + convertir, con
  feedback inline y disabled tooltips.
- **`/campaigns/page.tsx`** refactorizado de layout 2-col
  (form en Card + "Notas" en Card) a layout 3-zona vertical: header
  + form en sección con borde + `CampaignProgressCard` auto-oculta +
  `CampaignRunsTable` o empty state. Sugerencias de sector/región
  derivadas del histórico (ordenadas por frecuencia descendente).

### Fixed

- **Bug P0 nota obsoleta de `/campaigns`** ("ProspectorAgent está
  actualmente en stub. La implementación real llega en Fase 9") —
  mentira desde v0.2.0 cuando se implementó la integración real con
  Google Places. Detectada en la auditoría visual del dashboard.
  Test e2e regresivo añadido.

### Decisions

- **Reutilización de `LeadDetailPane`** entre master-detail y
  full-page — un único componente garantiza coherencia. Sin
  `sectorMedian` ni `percentile` en el full-page (requeriría fetch
  agregado adicional; el ScorePanel los omite silenciosamente).
- **Ventana 30 días por defecto para `/campaigns/runs`** (vs 7 días
  del audit-log) — las campañas son eventos menos frecuentes; un mes
  es la cadencia útil para revisar histórico.
- **`warnings_count` en lugar del array completo** en
  `CampaignRunSummary` — para badge sin payload pesado. El detalle ya
  vive en `/runs/{task_id}`.
- **Responsive de tabla por breakpoints** en lugar de scroll
  horizontal — columnas secundarias se ocultan elegantemente con
  `hidden md:table-cell` / `hidden lg:table-cell`.
- **3 tests vitest skipped por React 19 + happy-dom + useTransition**:
  side-effects post-`await` dentro de `startTransition(async)` no
  propagan de forma fiable en happy-dom. Cobertura real vive en
  Playwright cuando WCM-021 (MSW node) esté.

### Tests

- 448 pytest (+9 campaigns/runs endpoint).
- 77 vitest (74 pasan + 3 skipped React 19; +17 totales).
- 15 Playwright ejecutables (+6 nuevos campaigns) + 23 skipped
  (20 antiguos + 3 nuevos campaigns).
- ruff + tsc verde, 0 regresiones.

### Estado del rediseño

| Pantalla | Estado |
|---|---|
| `/login` | original |
| `/` Panel | ✅ v0.5.0 |
| `/campaigns` | ✅ **v0.6.0** |
| `/leads` master-detail | ✅ v0.4.0 |
| `/leads/[id]` full-page | ✅ **v0.6.0** |
| `/projects` + detalle | original (siguiente) |
| `/errors`, `/residual-tasks` | original |
| `/settings` | modelo a replicar |

---

## [0.5.0] — 2026-05-18

Rediseño completo de **Panel/Overview** — la primera pantalla tras
login. Sustituye las 4 KPI cards gigantes (3 con valor 0) y los 2
mensajes de placeholder ("Ningún proyecto en ejecución", "Sin errores
recientes") por una experiencia centrada en lo que de verdad pasa en el
sistema: **tira compacta de KPIs + feed de actividad agrupado por día**.

Sigue el mismo patrón de 5 bloques granulares que usamos en `/leads`
(v0.4.0). El componente `FilterChips` se compartió entre las dos
páginas tras el rediseño (movido a `components/`).

### Added

- **Endpoint `GET /api/v1/audit-log`** (rol any_user) para alimentar el
  feed. Hasta ahora `audit_log` solo se escribía desde 5 sitios
  (outreach, leads, webhooks); el dashboard no podía leerlo. Filtros:
  `action` (AuditAction enum), `entity_type`, `entity_id`, `actor`,
  `since` (ISO datetime), `limit` (1..200, default 50). Ventana por
  defecto: últimos 7 días. Ordenado por `at` DESC. 9 tests unit con
  inspección del SQL compilado (`literal_binds`).
- **3 componentes nuevos** en
  `apps/dashboard/src/app/(app)/_overview/`:
  - `OverviewKpiStrip` — tira horizontal con borde + divider sutil
    entre celdas. Cada celda con label uppercase small + value grande
    tabular-nums + `ArrowUpRight` si tiene `href`. Soporta `accent`
    para warning color en valores no-cero (errores). Responsive:
    `flex-wrap` + `min-w-[160px]` por celda.
  - `ActivityFeed` — agrupa eventos del audit_log por día con encabezado
    sticky ("Hoy", "Ayer", "Mar 17 may" en es-ES). Iconografía por
    action (Search / Fingerprint / Sparkles / Send / XCircle / ...
    via lucide-react), frases humanas en castellano ("Lead #42
    enriquecido", "Outreach enviado · Lead #19", "Proyecto #7
    desplegado"), actor en muted, tiempo relativo a la derecha.
    Enlaces inteligentes: lead → `/leads?selected={id}` (master-detail
    de v0.4.0), project → `/projects/{id}`, residual_task →
    `/residual-tasks`. Empty state explicativo si 0 eventos en 7 días.
  - `OnboardingCard` (inline en `page.tsx`) — sustituye al feed
    cuando el sistema está recién provisionado (0 leads + 0 proyectos
    + 0 eventos). Borde lima, copy explicativo del flujo
    (descubre → clasifica → enriquece, aprobación manual) y 2 CTAs:
    "+ Lanzar primera campaña →" + "Ver configuración del entorno".
- **Filtro del feed por action** con URL state `?action=enrich`. 7
  chips canónicos (descubrir, fingerprint, enriquecer, outreach,
  opt-out, deploy, sistema) reutilizando `FilterChips`. Header del
  feed muestra "X eventos · últimos 7 días · filtrado por <action>"
  cuando hay filtro activo.
- **Badge de entorno en Header global**: dot verde + "entorno · dev"
  o dot ámbar + "entorno · prod" según `process.env.NODE_ENV`.
  Sustituye al texto redundante "Migrator dashboard".
- **Spec Playwright** `tests/e2e/overview-redesign.spec.ts` con 8
  tests (2 ejecutables + 6 `test.skip(SSR_BLOCKED, "WCM-021")`).

### Changed

- **`apps/dashboard/src/app/(app)/page.tsx`** refactorizado de Server
  Component que renderiza 4 cards + 2 cards (~400 px de espacio
  desperdiciado con frases vacías) a Server Component que fetcha en
  paralelo `/leads/stats`, `/projects`, `/residual-tasks`, `/errors`,
  `/audit-log`, calcula `isEmptySystem` y delega a los componentes
  nuevos. Header: "Overview" → "Panel" (coherencia con sidebar).
- **`FilterChips` compartido entre páginas**: movido de
  `apps/dashboard/src/app/(app)/leads/_components/filter-chips.tsx` a
  `apps/dashboard/src/components/filter-chips.tsx` (genérico de URL
  state, no específico de leads). `git mv` preserva historial.
- **Visual baseline regenerada** para `dashboard overview` (la anterior
  capturaba la versión pre-rediseño).

### Decisions

- **Solo `audit_log` canon** alimenta el feed (no `error_log` ni
  cambios de status). Limpio, sin ruido técnico. Si necesitamos
  errors_log cruzado, se añade después como fuente opcional.
- **Agrupación por día con encabezado sticky** en lugar de timeline
  lineal — más fácil de escanear ("¿qué hicimos hoy?"). Las fechas
  > ayer usan formato corto es-ES via `toLocaleDateString`.
- **KPI strip con `flex-wrap`** sin breakpoints fijos — se adapta
  orgánicamente. La regla `idx > 0 → border-l` evita doble borde
  cuando los items envuelven a nueva fila.
- **Onboarding card como respuesta a "primer impacto vacío"** —
  decidimos no eliminar la pantalla para sistemas recién provisionados;
  mejor convertirla en un onboarding útil con CTAs reales.
- **Header env desde `NODE_ENV`** sin fetch adicional — el sidebar ya
  identifica el producto y la salud profunda vive en `/health/deep`.

### Tests

- 439 pytest (+9 audit-log endpoint).
- 60 vitest (+23: 21 componentes + 2 polish responsive).
- 9 Playwright ejecutables (+2 nuevos overview) + 20 skipped
  (14 antiguos + 6 nuevos del overview, pendientes WCM-021).
- ruff + tsc verde, 0 regresiones.

---

## [0.4.0] — 2026-05-16

Rediseño completo de `/leads`. Pasa de una tabla genérica de 8 columnas a
una experiencia **master-detail** estilo Linear/JetBrains: lista densa a la
izquierda, detalle vivo a la derecha que se actualiza al instante con la
selección. Tras una auditoría visual del dashboard entero, esta pantalla
fue la prioridad P1 absoluta (la más usada del producto, la de más
fricción). Sienta el nuevo lenguaje visual que extenderemos al resto en
releases posteriores.

Implementación en 5 commits granulares (`7ef97a9` → `b2ad4e7`) para
facilitar revisión por trozos.

### Added

- **`scripts/dev-status.sh`** sin cambios desde v0.3.0 (mencionado para
  contexto).
- **Endpoint `GET /api/v1/leads/stats`** — agregados para el topbar denso
  del rediseño: `total`, `uncontacted` (status pre-outreach), `avg_score`
  (excluye score=0), `distinct_builders` (excluye null/UNKNOWN),
  `distinct_sectors`, `distinct_regions`. Rol `any_user`. 3 tests unit
  con `AsyncMock side_effect` sobre las 6 ejecuciones SQL.
- **8 componentes nuevos** en `apps/dashboard/src/app/(app)/leads/_components/`
  (prefix `_` = no es route):
  - `ScorePanel` — cifra hero 60 px + barra horizontal con tick de
    mediana del sector + línea de contexto con percentil dentro del
    pipeline y delta vs sector.
  - `FingerprintList` — tech con barra de confianza inline y valor
    numérico.
  - `EvidenceTable` (client, toggle) — sustituye al dump JSON crudo de
    la versión anterior. Tabla compacta `Tech · Categoría · Confianza ·
    Evidencia` colapsable.
  - `ActivityTimeline` — eventos sobre línea vertical con dots
    lima/outline según sea positivo/neutro.
  - `TopbarStats` — tira densa `N leads · M sin contactar · score medio
    K · L builders` con dot opcional de salud del worker.
  - `FilterChips` (client) — chips toggle sincronizados con URL via
    `useSearchParams` + `router.replace`. Toggle exclusivo por param
    (patrón Linear). Preserva otros params (ej. `selected`) intactos.
  - `DraftBanner` — banner ámbar arriba del detalle cuando
    `lead.status === "outreach_prepared"`, con CTA "Revisar →".
  - `LeadActions` (client) — botones con onClick + feedback inline
    (loading/success/error). Conecta acciones reales contra backend.
  - `LeadList` (client) — items 50 px con dot lima/outline + score
    grande + nombre comercial + meta + tiempo relativo. Grupos "Sin
    contactar / Procesados" derivados del status. Selección con borde
    lima 2 px.
  - `LeadDetailPane` (presentacional) — score panel + acciones + 4
    secciones grid 2×2 (Contacto / Identificación / Fingerprint /
    Estado del flujo) + EvidenceTable + ActivityTimeline.
  - `LeadsWorkspace` (client) — orquestador master-detail. Layout
    edge-to-edge (`-m-6` anula padding del `<main>`), grid responsive
    (`grid-cols-1 xl:grid-cols-[420px_1fr]`), URL state con
    `?selected=N`, atajos teclado (`↑↓` navegan, `↵` abre full-page,
    `Esc` cierra detalle), construcción de chips de filtro a partir del
    set real (top 4 sectores, 3 builders, 3 regiones por frecuencia).
- **Helper `formatRelativeTime(iso)`** en `lib/utils.ts` — escala
  compacta es-ES ("ahora", "hace 12 min", "hace 3 h", "hace 5 d", "hace
  3 sem", "hace 6 mes", "hace 2 a").
- **Vitest plugin React enchufado** en `vitest.config.ts` (la dep ya
  estaba instalada pero no se usaba) — habilita JSX automatic runtime
  de React 19. Sin él, `renderToString` falla con "React is not defined"
  en componentes que no importan React explícitamente.
- **Dependencias de testing**: `@testing-library/react`,
  `@testing-library/jest-dom`, `@testing-library/user-event` (dev).
  Setup global en `tests/setup.ts` con cleanup automático.
- **27 tests Vitest nuevos** (12 smoke con `renderToString` + 10
  interactivos con userEvent + matchers jest-dom + 5 misc).
- **13 specs Playwright nuevas** (`tests/e2e/leads-redesign.spec.ts`):
  2 ejecutables hoy (`Escape limpia selección`, `Enter abre full-page`),
  11 marcadas `test.skip(SSR_BLOCKED, "WCM-021")` — documentan el
  contrato esperado y pasarán automáticamente cuando MSW node esté
  enchufado.

### Changed

- **`apps/dashboard/src/app/(app)/leads/page.tsx`** refactorizado de
  Server Component que renderiza tabla a Server Component que fetcha
  en paralelo `/leads` + `/leads/stats`, calcula medianas de score por
  sector en servidor y delega a `<LeadsWorkspace>` Client.
- **Sidebar** ancho `w-56` (224 px) → `w-[220px]` exactos. Versión
  hardcoded "v0.1" → "v0.3.0" (y ahora v0.4.0 en la siguiente actualización
  manual; pendiente automatizar via build var en v0.5+).
- **Visual baselines** de Playwright regeneradas (`dashboard overview`,
  `leads list`) para reflejar la versión master-detail.

### Fixed

- **CSS Grid + altura intrínseca**: el grid del master-detail con
  `align-items: stretch` por defecto crecía hasta los ~2000 px de la
  lista (29 items × ~50 px), sacando el panel detalle fuera del
  viewport. Fix: `overflow-hidden` + `min-h-0` en el grid + `min-h-0`
  en hijos con `overflow-y-auto` propio. Patrón estándar de scroll
  containers que aplicará al resto del dashboard.
- **React 19 SSR + interpolaciones JSX adyacentes**: `<strong>p{n}</strong>`
  produce `<strong>p<!-- -->{n}</strong>` con comments separadores.
  Componentes que requieren texto continuo usan template strings
  (`{`p${n}`}`).
- **Country `"ES"` → "España"** en la sección Identificación del detalle.
  Mapa `COUNTRY_LABELS` con fallback al código bruto si no está mapeado.
- **Teléfonos ES sin formato** → `+34 753 08 67 92` con regex
  `/^\+34(\d{9})$/`. Resto se devuelve tal cual.

### Decisions

- **Master-detail con preview live + selección por URL** elegida sobre
  la alternativa "tabla densa keyboard-first" porque el operador
  trabaja "en profundidad" (5-10 leads top por sesión) más que
  "barriendo masivo".
- **JetBrains Mono al 100%** (mantiene ADR-022 estricto, sin segunda
  tipografía) — la consistencia tipográfica refuerza el carácter
  "instrumento técnico".
- **Sidebar 220 px fijos** (sin toggle) — los operadores la quieren
  siempre visible para acceso rápido al resto del menú.
- **Empty state del detalle con stats agregados** (visibles / sin
  contactar / score medio / builders) — convierte un estado
  potencialmente vacío en información útil del filtro actual.
- **Acciones disabled visibles** ("Convertir a proyecto", "Marcar
  opt-out") con tooltip explicativo en lugar de ocultarlas: el
  operador ve qué acciones llegan y cuáles están pendientes.
- **Atajos teclado se enganchan al `document`** + ignoran si el target
  es input/textarea/select + ignoran si hay modificadores — no
  interfieren con la búsqueda fuzzy futura ni con copy/paste.
- **WCM-021 sigue abierto**: los 11 specs Playwright skipped quedan
  como documentación viva del comportamiento esperado. Cuando MSW node
  se implemente, flip de `SSR_BLOCKED = false` los activa de golpe.

### Tests

- 430 pytest (+3 stats endpoint).
- 37 vitest (12 smoke + 10 interactivos + 15 previos).
- 7 Playwright ejecutables + 14 skipped (3 antiguos + 11 nuevos).
- ruff + tsc verde, 0 regresiones.

---

## [0.3.0] — 2026-05-15

Release de DX local. Trae el comando `dev-status.sh` que faltaba para
diagnosticar la stack y, durante su primer uso, descubrió y resolvió el
bug raíz del venv en macOS — que llevaba dándonos guerra desde Fase 2
(ADR-016 atribuía la causa al sistema, pero el verdadero culpable era
iCloud Drive sincronizando el Desktop).

### Added

- **`scripts/dev-status.sh`** — comando de tipo `status` para la stack
  local. 3 modos:
  - Humano: tabla por secciones (servicios base / sesión tmux / procesos
    del stack / procesos sueltos) + resumen con totales OK/FAIL/WARN/SKIP.
  - `--quiet`: silencioso, solo exit code (útil en `&&`, cron o CI local).
  - `--json`: array de objetos `{status,section,service,detail}` para
    scripting.

  Comprobaciones:
  - `brew services` para `redis` y `postgresql@16`, con verificación de
    `redis-cli ping` y `pg_isready` (detecta el caso "started pero socket
    roto").
  - Existencia y nº de ventanas de la sesión tmux `wcm-dev`.
  - Por cada servicio (api/worker/beat/dashboard): ventana tmux viva +
    pid del proceso vía `pgrep -f` + HTTP probe en api y dashboard (acepta
    2xx/3xx — el dashboard redirige a `/login` con 307).
  - Detección de duplicados fuera de tmux (no chequea `next dev` porque
    arranca padre + hijo legítimos).

  Exit `0` si no hay FAIL; `1` si hay alguno; `2` si flag desconocido.
  Complementa a `wcm doctor` (que valida `.env` y TCP/HTTP a servicios
  externos) sin solaparlo.

### Changed

- **Venv local en macOS pasa a `venv.nosync/` con symlink `venv`**
  (ADR-035, supersede ADR-016). Todos los scripts y docs usan
  `venv/bin/python`, `venv/bin/uvicorn`, etc. — el symlink es
  transparente. En Linux/prod el cambio es cosmético: el venv se llama
  `venv/` directamente sin symlink y la doc de despliegue ya lo refleja.
- Referencias `.venv/` → `venv/` en `scripts/dev-up.sh`,
  `scripts/README.md`, `README.md`, `cli/README.md`, `docs/dev-local.md`,
  `docs/despliegue.md`, `docs/playbook-operativo.md`,
  `docs/release-v0.1.0.md`, `docs/security/audit-v0.1.0.md`,
  `infra/deploy/{deploy,migrate,rollback}.sh`,
  `.claude/agents/deployer-systemd.md`, `ruff.toml`. Un único nombre por
  toda la doc.
- `.gitignore` añade `venv.nosync/` y el symlink `venv`.

### Deprecated

- **`scripts/fix-venv-hidden-pth.sh`** queda como aviso de obsolescencia.
  Ya no aplica `chflags nohidden`: imprime una nota explicando ADR-035 y
  sale con exit 0. No se borra para no romper memoria muscular ni docs
  externas.

### Fixed

- **WCM-008 (`ModuleNotFoundError` en venv macOS, llevaba abierto desde
  Fase 2)** — diagnóstico real corregido. La causa no era la heurística
  "dot dir = hidden" de macOS, sino **iCloud Drive sincronizando
  `~/Desktop/`**: iCloud reaplicaba `UF_HIDDEN` sobre los `.pth` de
  editables cada <5 s, anulando el `chflags nohidden` antes de que
  arrancasen uvicorn/celery. Verificado empíricamente: un `.pth` en
  `/tmp/` mantiene el flag indefinidamente; el mismo `.pth` dentro de
  `.venv/` lo recupera en <5 s. xattrs `com.apple.fileprovider.dir#N`
  y `com.apple.fileprovider.pinned#PX` confirmaban la presencia del
  FileProvider de iCloud. Resuelto con `venv.nosync/` (sufijo .nosync =
  convención iCloud para excluir) + nombre sin punto (evita la heurística
  Finder). Tras el cambio, `dev-status.sh` da `8/8 OK, exit 0` desde el
  primer arranque sin pasos manuales.

### Decisions

- **ADR-035** "`venv.nosync/` con symlink `venv` para evitar el bug
  iCloud + dotted dir" (supersede ADR-016). Contexto, diagnóstico
  empírico y pasos de remediación en `docs/decisiones.md`.

### Tests

- **427 tests pasan** sin regresiones tras el rename del venv (suite
  completa en 22.78 s).

---

## [0.2.2] — 2026-05-14

### Fixed

- **`FingerprintResult.best_builder()` clasificaba mal WordPress + Elementor
  como `OTHER`**: la función filtraba solo `category == "builder"`, por lo
  que sitios WP+Elementor (caso real `aolcomunicacion.com`) devolvían
  Elementor como "best builder" — y Elementor no está en `BuilderType`, así
  que caía a OTHER. Ahora `best_builder()` aplica prioridad
  **cms > ecommerce > builder**: cuando coexisten un CMS (WordPress) y un
  builder dependiente (Elementor, Divi, Bricks), gana el CMS, porque la
  plataforma base es lo que importa para clasificar de cara a migración.
  Verificado: lead 13 (aolcomunicacion.com) re-clasificado de `OTHER` →
  `WORDPRESS` (conf 1.0) tras refingerprint. 2 tests nuevos en
  `test_fingerprint.py`.

---

## [0.2.1] — 2026-05-14

Hotfix: dos archivos polish que estaban en el working tree de la sesión
v0.2.0 pero **no llegaron a `git add`** al construir el commit del
release. CI y tests funcionaban porque el primero es cosmético y el
segundo está aislado de la suite que CI recorre.

### Added

- **`apps/api/tests/unit/test_campaigns_runs_endpoint.py`**: 8 tests
  unitarios del endpoint `GET /api/v1/campaigns/runs/{task_id}` con
  `AsyncResult` mockeado (estados PENDING, STARTED, FAILURE, SUCCESS
  con/sin leads, payload `status=error`, auth viewer ok, 401 sin auth).
  Mencionados en el changelog de v0.2.0 pero el archivo no estaba en
  el repo.

### Fixed

- **`tailwind.config.ts` `muted.foreground`**: quedó como `#7d6552`
  (marrón de la paleta antigua) cuando todo el resto pasó a azul marino
  en v0.2.0. Corregido a `#56657A` (azul gris medio). Detectado al ver
  componentes shadcn-style con foreground marrón sobre fondo oscuro.

---

## [0.2.0] — 2026-05-14

Primera iteración tras testeo funcional real. Trae visualización rica del
progreso de campaña, indicador global multiventana, internacionalización,
nuevo modelo de datos `Campaign`, paleta de marca rediseñada y varios
fixes P0 detectados al usar el producto.

### Added

- **`scripts/README.md`**: documentación de los controles del stack local
  (`dev-up.sh`, `dev-down.sh`, `fix-venv-hidden-pth.sh`) con atajos `tmux`,
  patrones de uso típicos y troubleshooting.
- **Task Celery `wcm.enricher.run`**: expone `EnricherAgent` como task
  reutilizable (WCM-027). Acepta `skip_embedding` opcional.
- **Endpoint `POST /api/v1/leads/{id}/enrich`** + CLI `wcm leads enrich`
  (WCM-027). Rol operator/admin.
- **Página `/campaigns/runs/[task_id]`**: progreso vivo de una campaña con
  endpoint `GET /api/v1/campaigns/runs/{task_id}` + componente cliente con
  polling cada 2s. Visualización rica con 3 nodos animados (Descubrimiento
  → Identificación → Enriquecimiento), conectores con flujo y stats.
- **Tabla `campaigns`** en BD + modelo SQLAlchemy `Campaign`. Persiste
  cada lanzamiento con `task_id`, parámetros, estado agregado,
  `created_lead_ids`, timestamps y `created_by_user_id`. FK
  `lead.campaign_id`. Migración Alembic `c8e1dc21716b`.
- **Endpoint `GET /api/v1/campaigns/active`**: lista campañas no terminadas.
  Cualquier rol. Sirve al indicador global del dashboard.
- **`ActiveCampaignsIndicator`** en el header del dashboard: pildora lima
  con loader + sector/región que aparece cuando hay 1+ campañas en curso.
  Polea cada 5s. **Multiventana real** (lee de BD, no localStorage).
- **Sidebar y status traducidos a castellano** vía `lib/labels.ts`. 8
  ubicaciones afectadas: overview, leads (list+detail), projects (list+
  detail+checklist), residual-tasks, run-status. Helper centralizado
  cubre `LeadStatus`, `ProjectStatus`, `ProjectPhaseStatus`,
  `ResidualStatus`, `OutreachSequenceStatus`.
- 18 tests nuevos: `test_campaigns_runs_endpoint`, `test_tasks_pipeline`,
  `test_campaigns_persistence`, `test_leads_pipeline_endpoints`, +
  ampliación en `test_prospector` (created_lead_ids, place_details) y
  `test_imports` (campaigns).

### Changed

- **Paleta de marca**: sustituida la paleta marrón original por azul
  marino casi gris (`#0E1218` / `#1A222D` / `#E2E8F0` / `#3D4A5C`). Mejor
  contraste para tablas densas + look técnico (referencia visual: Linear
  / JetBrains dark). El acento lima `#B1F100` se mantiene intacto.
  `tailwind.config.ts`, `globals.css` y `CLAUDE.md §3` actualizados.
- **Pipeline de enrich**: `tasks/prospector.run_campaign` ya no usa
  `celery.chain(fingerprint, enrich)` sino dos `send_task` independientes
  por lead. Motivo: si fingerprint fallaba (URL inalcanzable, timeout),
  el chain rompía y enrich nunca corría → lead atascado en `DISCOVERED`
  → Campaign atascada en `RUNNING` para siempre. Ahora `enrich` corre
  aunque fingerprint falle (coste: el score no contará builder detectado
  en ese lead).
- **CI**: `tsconfig` con `noUncheckedIndexedAccess` ya forzaba narrowing
  estricto; el código nuevo lo respeta. Tests Python con cobertura
  86.87% (umbral 70%).

### Fixed

- **WCM-026 (P0)**: `ProspectorAgent` no encadenaba fingerprint + enrich
  tras crear leads. Ahora `tasks/prospector.run_campaign` itera
  `outputs["created_lead_ids"]` y encola fingerprint+enrich por lead.
- **WCM-028**: warning estático obsoleto en `wcm campaigns launch`
  ("ProspectorAgent es stub en Fase 6") reemplazado por mensaje real.
- **WCM-032 (P0)**: dashboard no podía autenticar contra el API
  ("Credenciales no proporcionadas") porque `get_current_user_payload`
  no leía la cookie `wcm_session` — el middleware que el comentario
  prometía nunca se implementó. La dependency ahora recibe `Request` y
  lee `request.cookies.get(settings.session_cookie_name)` como fallback.
- **WCM-033**: worker Celery hacía SIGSEGV al cargar
  `intfloat/multilingual-e5-large` en macOS con `--pool=prefork`
  (PyTorch + `fork()` no se llevan bien). `scripts/dev-up.sh` arranca
  ahora con `--pool=threads --concurrency=2`. En Linux/prod sigue siendo
  prefork.
- **Race condition `POST /launch` ↔ worker**: el worker podía coger la
  task **antes** de que la fila `campaigns` estuviera committed, dejando
  la Campaign atascada en `QUEUED` con `created_lead_ids={}` y los leads
  sin `campaign_id`. Fix: el endpoint genera el `task_id` con
  `uuid.uuid4()`, commitea la fila primero y luego encola con
  `celery_app.send_task(..., task_id=task_id)` que fuerza ese ID. Test de
  regresión basado en `await_count` de `session.commit`.

### Operational notes

- Cobertura: 86.87% (407 passed, 10 skipped).
- Stack canónico confirmado: Node 22 LTS (`@node@22` brew formula), Python
  3.14, Postgres 16 + pgvector 0.8.0, Redis 8, sin Docker.
- Repo movido a `~/Desktop/` y desactivado el evict de iCloud Drive
  ("Conservar en este dispositivo") para evitar archivos `dataless` —
  raíz del incidente de pack git corrupto + venv `.pth` re-ocultando.

---

---

## [0.1.1] — 2026-05-14

Primer patch release tras testeo funcional local. Descubre y arregla un **bug P0 de runtime** que impedía que la prospección produjera leads, más mejoras de DX y documentación.

### Fixed

- **ProspectorAgent**: Google Places Text Search legacy NO devuelve `website` ni `phone` — solo `place_id`, `name`, `address`, `types`. El código filtraba con `if not place.website` que SIEMPRE era `None` → **ningún lead se creaba en producción**. Fix: `place_details(place_id)` adicional por cada place que pasa el filtro de tipo, mergeando los campos extendidos. Verificado con campaña real "restaurante / Cáceres / target=5" → 5 leads con URLs reales. WCM-031.

### Added

- **`docs/dev-local.md`**: quickstart end-to-end para correr la stack en macOS (sin Docker). Cubre pre-requisitos brew (pgvector compilado contra @16), creación de BD, migraciones, seed admin, arranque de los 4 procesos, smoke test del flujo prospección, validaciones post-test, troubleshooting.
- **`scripts/dev-up.sh`** y **`scripts/dev-down.sh`**: orquestación tmux para arrancar/parar toda la stack con un solo comando. WCM-023.
- **`.gitignore`**: añadido `celerybeat-schedule*` (artefactos runtime del Celery beat).

### Discovered (issues abiertos para próximas releases)

- WCM-022: comando `wcm users create` (admin seed sin script ad-hoc).
- WCM-024: flag `--macos-local` en `infra/whm-setup/02-database.sh`.
- WCM-025: ADR-034 documentando GlitchTip vs Sentry.
- **WCM-026 (P0)**: `ProspectorAgent` no encadena fingerprint+enrich tras crear leads.
- **WCM-027 (P0)**: falta task Celery `wcm.enricher.run` + endpoint API `/leads/{id}/enrich` + CLI `wcm leads enrich`.
- WCM-028: warning estático obsoleto en `wcm campaigns launch`.
- WCM-029: `.env.example` debe usar `postgresql+psycopg://` (psycopg v3) en `DATABASE_SYNC_URL`.
- WCM-030: añadir `greenlet>=3.0` a deps explícitas del API (lo requiere SQLAlchemy async).

### Operational notes

- GlitchTip hosted validado como backend Sentry-compatible (free 1k eventos/mes, drop-in con `sentry-sdk`).
- Validado primer flujo real Google Places → 5 leads cualificados con emails/phones/socials/score → outreach LSSI-CE compliant (validador legal v1.0, JWT opt-out firmado).

---

## [0.1.0] — 2026-05-14

Primer release del MVP. Cubre el alcance completo de las **16 fases de construcción** (0–15) con producto funcional, documentación operativa y tooling de despliegue.

### Added — productos

- **Prospección comercial automatizada** end-to-end:
  - Descubrimiento vía Google Places API legacy (ADR-024).
  - Fingerprinting Wix / Hostinger AI / Webflow / WordPress.
  - Enriquecimiento con emails, teléfonos, socials + **embedding semántico 1024d** (sentence-transformers `intfloat/multilingual-e5-large`, ADR-023).
  - Composición de outreach LSSI-CE compliant con validador legal v1.0.
  - Envío vía Resend con doble-check anti-opt-out (ADR-025).
  - Webhook entrante para opens/bounces/replies.
- **Migración técnica** Wix/Hostinger AI/Webflow → WordPress + Bricks Builder:
  - Orchestrator con **15 fases** (`scrape_origin → extract_content → preserve_seo → optimize_assets → detect_multilang → transpile_bricks → deploy_wp → migrate_woo → configure_wpml → rebuild_forms → visual_diff → qa → generate_checklist → sync_clickup → notify`).
  - Stub agents para fases post-MVP (woo, wpml, forms, visual-diff, qa, checklist).
  - Asset optimizer con Pillow → WebP q82 + upload R2 (ADR-026).
- **Cumplimiento legal RGPD/LSSI-CE** integrado en pipeline:
  - 4 documentos legales en `apps/api/legal/`.
  - Opt-out funcional con un clic (JWT firmado, link en todos los emails).
  - `opt_out_log` permanente (nunca se borra).
  - Política de retención automática (cron Celery beat 03:30 diario).
  - AuditLog con `legal_ground=6.1.f` en cada acción.

### Added — apps

- **`apps/api`** (FastAPI):
  - 30+ endpoints REST con JWT + cookie http-only.
  - RBAC con 3 roles (admin / operator / viewer).
  - Webhooks ClickUp + Resend con verificación HMAC.
  - Rate limiting con `slowapi` en endpoints sensibles.
- **`apps/worker`** (Celery):
  - 21 subagentes runtime (12 reales + 9 stub).
  - Celery beat para retention sweep.
  - Integraciones ClickUp / Resend / R2.
- **`apps/dashboard`** (Next.js 15 + React 19 + shadcn):
  - 10 páginas funcionales con JetBrains Mono (ADR-022).
  - Server components + cookie http-only.
  - Visual regression tests con Playwright.
- **`cli/`** (Typer + Rich):
  - Doble entrypoint `webcafeina-migrator` y `wcm` (ADR-021).
  - 11 grupos de comandos.

### Added — observabilidad

- **structlog** central (JSON en prod, ConsoleRenderer en dev).
- **Sentry SDK** perezoso en api / worker / dashboard (ADR-028).
- **Logtail** handler opcional.
- **Prometheus** con registry propio + endpoint `/metrics` (ADR-029).
- **`/health/deep`** verifica Postgres + Redis + R2.

### Added — infra

- **systemd nativo** sin Docker (ADR-001/030): 4 units con hardening completo + target agregado.
- **Nginx** vhosts con HSTS / CSP / TLS 1.2-1.3 / ACL para `/metrics` y `/health/deep`.
- **5 scripts WHM setup** idempotentes (Python 3.14 + Node 22 + Redis + PG+pgvector + envsubst + secrets auto).
- **4 scripts deploy** con rollback automático y health-check post-deploy.
- **2 GitHub Actions workflows**: CI matrix Python 3.13/3.14 × Node 20/22 + deploy-production SSH.

### Added — tests

- **387 tests Python** + **15 TypeScript** + **8 Playwright** = **410 tests**.
- **Coverage Python: 74.8%** (threshold 70% en CI).
- E2E Playwright dashboard con API 100% mockeada via `page.route()`.
- E2E pipeline Python con `Orchestrator` real y `stateful_session` (ADR-032).
- Tests de validación infra (`bash -n`, configparser systemd, security headers, ACL).
- Visual regression con `expect(page).toHaveScreenshot()`.

### Added — documentación

- `docs/arquitectura.md` con **8 diagramas Mermaid** + tabla de los 21 subagentes.
- `docs/prospeccion.md` (10 secciones operador).
- `docs/migracion.md` (13 secciones operador).
- `docs/playbook-operativo.md` con **10 runbooks INC-NN**.
- `docs/glossary.md` con **40+ términos** alfabetizados.
- `docs/despliegue.md` runbook completo (12 secciones).
- `docs/performance.md` SLOs + cómo medir.
- `docs/security/audit-v0.1.0.md` security review final.
- `docs/decisiones.md` con **33 ADRs**.

### Decisions (ADRs)

- ADR-001: sin Docker, todo systemd nativo.
- ADR-010 → **ADR-023**: embeddings con `sentence-transformers` + `multilingual-e5-large` (supersede Voyage AI).
- ADR-013: push del repo GitHub diferido al final (cumplido en este release).
- ADR-017: proxy layered free→paid (NoProxy → Webshare → ScraperAPI → Bright Data).
- ADR-020: subagentes runtime `apps/worker/.../agents/` distintos de descriptors `.claude/agents/`.
- ADR-022: JetBrains Mono en toda la UI.
- ADR-024: Google Places API legacy (no New).
- ADR-025/26/27: Resend / R2 vía boto3 / ClickUp tag-based sync.
- ADR-028/29: observabilidad perezosa + Prometheus registry propio.
- ADR-030/31: systemd hardening + single-server WHM.
- ADR-032: e2e strategy Playwright + pipeline.
- **ADR-033**: hardening philosophy (este release).

### Security

- 0 vulnerabilidades en `pip-audit` (270+ deps Python).
- 1 vulnerabilidad transitiva resuelta vía `pnpm overrides`: `postcss < 8.5.10` → `^8.5.10`.
- Headers Nginx: HSTS preload, CSP restrictiva, X-Frame-Options DENY, Referrer-Policy strict-origin-when-cross-origin, Permissions-Policy.
- HMAC `compare_digest` en todos los webhooks (no timing attacks).
- Sentry con `send_default_pii=False`.
- Rate limit: login 5/min, outreach compose 10/min, send 30/min, opt-out-url 30/min.
- Cookie `wcm_session` HttpOnly. (Pending: confirmar `Secure` + `SameSite=Lax` en primer deploy — WCM-016.)

### Known issues / pendientes post-v0.1.0

| ID | Descripción |
|---|---|
| WCM-011 | Revisión legal externa de plantillas outreach |
| WCM-013 | Columna `retention_hold` para excepciones AEPD |
| WCM-014 | Idempotency keys en POST con side-effects externos |
| WCM-015 | `pip-audit` + `pnpm audit` en CI workflow |
| WCM-016 | Verificar `Secure` + `SameSite=Lax` en cookie de prod |
| WCM-017 | Migrar slowapi a storage Redis para multi-nodo |
| WCM-018 | Lighthouse CI en GitHub Actions |

### Stack final

- **Backend**: Python 3.14 / FastAPI / SQLAlchemy 2.x / Celery 5.4 / Redis 7
- **DB**: PostgreSQL 16 + pgvector
- **Frontend**: Next.js 15 / React 19 / TypeScript 5 / Tailwind 3.4 / shadcn/ui
- **Workers**: 21 subagentes Python
- **Despliegue**: systemd nativo en WHM/cPanel (sin Docker)
- **Observabilidad**: structlog + Sentry + Logtail + Prometheus
- **Tests**: pytest + Vitest + Playwright + pytest-cov

### Equipo

Webcafeína S.L. (CIF B10463990). Cáceres, España. Equipo de 9 personas; el proyecto se mantiene como equipo único sin roles individuales asignados.

---

## Convenciones del Changelog

- **Added** — nueva funcionalidad
- **Changed** — funcionalidad existente modificada
- **Deprecated** — funcionalidad que se retirará en una versión futura
- **Removed** — funcionalidad eliminada
- **Fixed** — bugs corregidos
- **Security** — correcciones de seguridad

Cada versión enlaza al commit/tag correspondiente en GitHub una vez el repo esté publicado (ADR-013).
