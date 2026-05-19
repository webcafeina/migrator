# Flujo de migración — explicación operativa paso a paso

> **Documento vivo.** Esta guía explica el flujo completo de migración tal y como
> funciona en la versión actual del producto. Cada vez que el flujo cambie (nueva
> fase, fase eliminada, refactor de un agente, cambio de comportamiento), **este
> documento debe actualizarse en el mismo commit que modifica el código**.
> Si lees algo aquí que ya no coincide con la realidad, abre PR con el ajuste.
>
> Referencia inicial: cubre desde v0.19.0 (release 2026-05-19). Pendiente
> actualizar si entra v0.20.0+ con cambios en alguna fase.

---

## Índice

1. [Qué es un proyecto de migración](#paso-1--qué-es-un-proyecto-de-migración)
2. [Wizard `/projects/new` (4 pasos)](#paso-2--wizard-projectsnew-4-pasos)
3. [El pipeline arranca y procesa las 15 fases](#paso-3--el-pipeline-arranca-y-procesa-las-15-fases)
4. [Modos del origen y la fase `scrape_origin`](#paso-4--modos-del-origen-y-la-fase-scrape_origin)
5. [Fases `extract_content` y `preserve_seo`](#paso-5--fases-extract_content-y-preserve_seo)
6. [Fases preparatorias para Bricks (`optimize_assets`, `detect_multilang`, `transpile_bricks`)](#paso-6--fases-preparatorias-para-bricks-optimize_assets-detect_multilang-transpile_bricks)
7. [Fase `deploy_wp` (la primera que toca el WP destino)](#paso-7--fase-deploy_wp-la-primera-que-toca-el-wp-destino)
8. [Fases condicionales y verificación visual (`migrate_woo`, `configure_wpml`, `rebuild_forms`, `visual_diff`)](#paso-8--fases-condicionales-y-verificación-visual-migrate_woo-configure_wpml-rebuild_forms-visual_diff)
9. [Las 3 últimas fases: QA, entregable y cierre (`qa`, `generate_checklist`, `sync_clickup`+`notify`)](#paso-9--las-3-últimas-fases-qa-entregable-y-cierre-qa-generate_checklist-sync_clickupnotify)
10. [Rollback y modos de recuperación](#paso-10--rollback-y-modos-de-recuperación)
11. [Resumen visual de los 10 pasos](#resumen-de-los-10-pasos-del-flujo)
12. [Notas para la primera prueba real](#notas-para-la-primera-prueba-real)

---

## Paso 1 — Qué es un proyecto de migración

Un **proyecto** en este sistema es la unidad de trabajo: una migración concreta
de **una web origen → un WordPress destino con Bricks Builder**. Vive en la
tabla `projects` y tiene un ciclo de vida fijo de status:

```
queued → running → completed
                ↘ qa_failed → resume / rollback / cancelled
                ↘ blocked_human_input → resume / cancelled
                ↘ cancelled
                                                 ↘ rolled_back  (terminal, v0.19.0)
```

### Información mínima que un proyecto necesita para arrancar

| Campo | De dónde sale | Obligatorio |
|---|---|---|
| `source_url` | el wizard o el lead origen | sí |
| `client_name` | el operador (o pre-rellenado del lead) | sí |
| `target_domain` | el operador (subdominio o dominio del cliente) | sí en el wizard |
| `builder_source` | auto-detectado por `fingerprinter` o seleccionado en el wizard | no (se puede dejar vacío) |
| `has_ecommerce`, `is_multilang`, `preserve_paths` | checkboxes del wizard | flags, default sensatos |
| `source_access_mode` + `source_credentials_encrypted` | opcional, si el cliente nos dio API key Wix/Webflow | no |

### Cómo nace un proyecto (dos rutas hoy)

1. **Desde un lead cualificado** — en `/leads/[id]`, botón "Convertir a proyecto"
   navega a `/projects/new?lead_id=N` y el wizard pre-rellena URL + builder +
   nombre cliente.
2. **Directo** — desde `/projects`, botón "+ Nuevo proyecto" abre `/projects/new`
   en blanco.

Ambas rutas terminan en el **mismo wizard** (4 pasos). El wizard crea el
`Project` en el último paso, ejecuta el preflight, y solo entonces ofrece el
botón "Crear y arrancar" (que dispara el pipeline).

### Lo crítico: el proyecto NO arranca solo

Tras crear el proyecto, el pipeline queda en `queued`. El operador tiene que
**pulsar Start** explícitamente (o "Crear y arrancar" en el wizard tras el
preflight). Decisión consciente: hay que decidir si arrancar tras revisar los
chequeos previos.

---

## Paso 2 — Wizard `/projects/new` (4 pasos)

El wizard es **Client Component** con `useState` propio (sin librería de
wizards). Tiene un stepper superior con 4 chips. Cada paso valida sus campos
antes de habilitar "Siguiente". El proyecto NO se crea hasta el paso 4.

### Paso 1 — Origen

| Campo | Validación | Notas |
|---|---|---|
| **URL del origen** * | http(s) válido | Inhabilita "Siguiente" si no es URL HTTP(S) |
| **Nombre del cliente** * | no vacío | Pre-rellenado con `lead.business_name` si vienes de un lead |
| **Builder origen** | select 7 opciones | wix, webflow, hostinger_ai, wordpress, squarespace, shopify, other — opcional, el pipeline lo re-detectará si lo dejas vacío |

**Panel condicional "credenciales del back"** — solo aparece si
`builder ∈ {wix, webflow}`. Es un checkbox opcional. Si lo activas, te pide:

- Wix: `api_key` (password input) + `site_id`
- Webflow: `api_token` (password input) + `site_id`

Las credenciales se cifran con Fernet **antes** de persistirse (lo hace el
endpoint del paso 4) y nunca se devuelven en claro en `ProjectRead`. El campo
`password` evita ojos curiosos en pantalla.

### Paso 2 — Destino

Un único campo: **`target_domain`** obligatorio
(ej. `migracion-cliente.webcafeina.com`).

Nota fija debajo: las credenciales del WP destino (`WP_DEFAULT_*` en `.env` —
SITE_URL, REST_USER, REST_APP_PASSWORD, HOST, SSH_USER, SSH_KEY_PATH) se
verificarán en el paso 4. El wizard no las pide al operador porque son de
servidor (no de cliente).

### Paso 3 — Features

Tres checkboxes:

- **Tiene tienda online** → activa `has_ecommerce=true` (la fase `migrate_woo`
  se ejecutará).
- **Multilang** → `is_multilang=true` (la fase `configure_wpml` se ejecutará —
  sin licencia WPML, generará residual manual).
- **Preservar paths** → `preserve_paths=true` por defecto (recomendado para
  SEO; URLs idénticas a origen).

### Paso 4 — Crear + Preflight

Este paso tiene dos estados:

**(a) Antes del primer click** — botón único "Crear proyecto y ejecutar
preflight". Al pulsarlo, el wizard hace 3 cosas en cadena:

1. `POST /api/v1/projects` con todos los campos recopilados → crea el `Project`
   en BD.
2. Si introdujiste credenciales del back →
   `PUT /api/v1/projects/{id}/source-credentials` (admin-only; si no eres
   admin, falla silencioso y el modo queda `none`).
3. `POST /api/v1/projects/{id}/preflight` → ejecuta los 4 chequeos en paralelo
   (timeout 10s c/u, total ≤10s).

**(b) Tras el preflight** — aparece `<PreflightDisplay>` con 4 cards:

| Check | Bloqueante | Verifica |
|---|---|---|
| **WP destino** | sí | `GET /wp-json/` + TCP banner SSH al puerto 22 |
| **Plugins** | parcial (ver nota) | HEAD a `/wp-json/{bricks,gf/v2,wc/v3}/` |
| **Origen** | sí | `GET source_url` con redirects, espera HTTP 2xx-3xx |
| **Credenciales back** | no, warning | Llamada barata a Wix/Webflow API (si se introdujeron) |

> **Plugins — ADR-037**: Bricks Builder es **bloqueante** (sin él el deploy
> deja páginas vacías porque el contenido vive en el post meta
> `_bricks_page_content_2` que solo Bricks renderiza). Gravity Forms y
> WooCommerce son **informativos** — el pipeline degrada con ResidualTask
> claras si faltan, sin perder valor del deploy.

Si algún chequeo **bloqueante** falla, aparece como rojo en su card + lista al
pie en sección "Bloqueantes (N)". El botón "Crear y arrancar pipeline" queda
**deshabilitado** hasta que resuelvas todos los bloqueantes y re-ejecutes el
preflight.

Si todo OK, hay 3 botones:

- **"Crear y arrancar pipeline"** (verde lima) →
  `POST /api/v1/projects/{id}/start` + redirige a `/projects/{id}` para ver el
  pipeline corriendo.
- **"Re-ejecutar preflight"** → vuelve a lanzar el endpoint sin crear nada
  (útil tras corregir un envs).
- **"Guardar sin arrancar"** → solo redirige a `/projects/{id}` con el proyecto
  en `queued`. El operador lo arrancará después.

### Edge case importante

Si el operador **cancela** el wizard entre paso 3 y paso 4, el proyecto NO
existe (no se ha llamado a `POST /projects`).

Si cancela **después** del paso 4 (proyecto ya creado pero sin arrancar), queda
en BD con `status=queued` y se puede retomar desde `/projects/{id}` → botón
"Start".

### Persistencia del preflight

El resultado del preflight se guarda en `projects.preflight_results_json` +
`projects.preflight_at`. Si el operador vuelve al proyecto 3 minutos después,
puede consultar el último preflight sin re-ejecutarlo. Re-ejecutar lo
sobrescribe.

---

## Paso 3 — El pipeline arranca y procesa las 15 fases

### 3.1 Encolado

Cuando pulsas "Start" (UI), "Crear y arrancar" (wizard) o
`wcm projects start ID` (CLI), el API hace:

1. Marca `project.status = RUNNING` + `started_at = now()`.
2. Llama `enqueue_project_pipeline(project_id)` →
   `celery_app.send_task("wcm.orchestrator.run_project", kwargs={"project_id", "resume"})`.
3. Devuelve `{task_id, status: "queued", project_id}` con 202 Accepted.

El API **no ejecuta nada inline** — solo persiste el cambio de status y deja el
job en la cola Redis. El worker Celery (proceso separado) lo recoge.

> **Próximo cambio (ADR-048 — programado para v0.20.0+)**: `POST /start`
> pasará a **re-ejecutar siempre el preflight** antes de encolar. Si
> `can_start=False` → 409 con detalle, NO arranca. Invariante "el pipeline
> NUNCA arranca sin preflight fresh OK". Penalty UX ~10s por Start, pero
> evita arrancar con bloqueantes olvidados (operador que hizo "Guardar sin
> arrancar" hace 1h con bloqueantes y luego pulsa Start). `/resume` se
> mantiene SIN re-preflight (es reintento, no arranque nuevo).

### 3.2 El Orchestrator

`apps/worker/src/wcm_worker/pipeline.py` define una lista declarativa de fases:

```
_DEFAULT_PHASES = (
  (phase_name,              agent_class,            required, condition_attr)
  ─────────────────────────────────────────────────────────────────────────────
  ("scrape_origin",         ScraperOriginAgent,     True,     None),
  ("extract_content",       ContentExtractorAgent,  True,     None),
  ("preserve_seo",          SeoPreserverAgent,      True,     None),
  ("optimize_assets",       AssetOptimizerAgent,    False,    None),
  ("detect_multilang",      MultilangHandlerAgent,  True,     None),
  ("transpile_bricks",      BricksTranspilerAgent,  True,     None),
  ("deploy_wp",             WpDeployerAgent,        True,     None),
  ("migrate_woo",           WooMigratorAgent,       False,    "has_ecommerce"),
  ("configure_wpml",        WpmlConfiguratorAgent,  False,    "is_multilang"),
  ("rebuild_forms",         FormsRebuilderAgent,    False,    None),
  ("visual_diff",           VisualDiffAgent,        False,    None),
  ("qa",                    QaRunnerAgent,          False,    None),
  ("generate_checklist",    ChecklistGeneratorAgent,False,    None),
  ("sync_clickup",          ClickupSyncerAgent,     False,    None),
  ("notify",                ResendNotifierAgent,    False,    None),
)
```

El **Orchestrator** recorre esta lista **en orden**, fase por fase, dentro de
UNA sesión SQLAlchemy. Una única transacción larga (no paralelismo entre fases —
paralelismo solo intra-fase si el agente lo necesita).

### 3.3 Decidir si saltar una fase

Para cada `_PhaseSpec`, el orchestrator pregunta:

```
_should_run(spec, project):
  - condition_attr is None         → True (siempre corre)
  - condition_attr="has_ecommerce" → corre solo si project.has_ecommerce
  - condition_attr="is_multilang"  → corre solo si project.is_multilang
```

Si decide no ejecutar:

- Marca la fase como **SKIPPED** con summary "condition no cumplida".
- Pasa a la siguiente.

Caso típico: proyecto corporativo sin ecommerce → `migrate_woo` se salta
directamente sin invocar al agent.

### 3.4 Ejecutar una fase

Cuando sí corre:

```
1. _mark_phase(phase_name, RUNNING)       ← upsert en project_phases + publish SSE
2. agent = AgentClass()
3. ctx  = AgentContext(session, project_id)
4. result = agent.run(ctx)                ← lógica del agente, modifica BD
5. _mark_phase(phase_name, COMPLETED,
               summary=result.summary,
               outputs=result.outputs)    ← upsert + publish SSE
```

`_mark_phase` hace **upsert** en `project_phases` (UNIQUE por
`project_id + phase_name`). En el re-intento, incrementa `attempt`. Tras
escribir BD, publica al canal Redis `wcm:project:{id}:events` para que el
dashboard se entere al instante.

### 3.5 Manejo de errores (4 caminos posibles)

| Excepción del agent | Fase `required=True` | Fase `required=False` |
|---|---|---|
| **`AgentNotImplementedError`** | imposible — todas las required están implementadas v0.17.0+ | marca SKIPPED + warning + sigue |
| **`AgentError` tipado** (ScraperOriginError, etc.) | marca FAILED + `project.status=BLOCKED_HUMAN_INPUT` + **aborta el pipeline** | marca FAILED + `outcome.failed_phase` registrado + sigue con la siguiente |
| **`Exception` genérico** | marca FAILED + BLOCKED + aborta | marca FAILED + BLOCKED + aborta (más conservador) |
| **(éxito)** | COMPLETED + sigue | COMPLETED + sigue |

> **Próximo cambio (ADR-049 — programado para v0.20.0+)**: la fila
> "`Exception` genérico + `required=False`" pasará a **continuar** (mismo
> comportamiento que `AgentError` en no required). El flag `required`
> gobernará lo que para o no, no el tipo de excepción. Una imagen corrupta
> en `optimize_assets`, un Chromium crash en `visual_diff` o un W3C
> validator caído en `qa` ya no abortarán el pipeline entero — quedarán
> como `failed_phase` para diagnóstico pero el resto sigue. `required=True`
> mantiene el comportamiento conservador (aborta).

### 3.6 Estado final del proyecto

Tras procesar las 15 fases, el orchestrator decide el status final:

- Sin failed_phase → `COMPLETED` + `completed_at = now()`.
- Con `failed_phase` (de una fase NO required) → `QA_FAILED`. El proyecto sigue
  siendo entregable; el operador revisa el checklist y decide.
- Con `failed_phase` (required) → `BLOCKED_HUMAN_INPUT`, ya marcado al saltar
  de la transacción.

### 3.7 Resume

Si pulsas "Resume" en `qa_failed` o `blocked_human_input`:

- API marca `project.status = RUNNING` y encola la misma task con `resume=True`.
- El orchestrator **reejecuta la lista entera**. Como `_mark_phase` es upsert,
  las fases ya COMPLETED simplemente actualizan timestamp (no rompen). Las
  pendientes se ejecutan.
- En la práctica, lo más común es que solo se reintenten las FAILED y se
  completen las pendientes. Las COMPLETED son idempotentes (re-deploy WP →
  upsert por slug, no duplica).

> **Próximo cambio (ADR-043 — programado para v0.20.0+)**: Resume saltará
> las fases COMPLETED por defecto, ejecutando solo las que faltan. Para
> una migración de 30 páginas que falló en `qa`, el Resume rápido tarda
> ~1-2 min (qa + checklist + clickup + notify) en lugar de ~15 min (lista
> entera idempotente). El operador podrá marcar un toggle "Re-ejecutar
> todo desde el principio" en el botón Resume (UI), pasar
> `--force-rerun-all` (CLI) o `?force_rerun_all=true` (API) para forzar
> el comportamiento actual cuando sospeche corrupción.

### 3.8 Lo que ves desde fuera mientras corre

Tres canales en tiempo real, todos partiendo del mismo `_mark_phase`:

1. **BD** — tabla `project_phases` con el estado de cada una de las 15 fases
   (pending/running/completed/skipped/failed).
2. **SSE** — canal Redis emite
   `{kind:"phase", project_id, phase_name, status, summary, ts}` que el
   dashboard escucha.
3. **Logs structlog** — `wcm.worker.pipeline` con
   `phase_skipped_not_implemented`, `phase_failed`, etc.

El dashboard muestra los 15 dots del `PipelineStepper` con su estado actual y
hace tooltip con duración + summary al pasar el ratón. En vista fleet, los 15
dots se colapsan a 5 buckets (scrape/transpile/deploy/qa/notify).

---

## Paso 4 — Modos del origen y la fase `scrape_origin`

### 4.1 Los 3 modos

`projects.source_access_mode` admite 3 valores (CHECK constraint en BD):

| Modo | Cuándo | Qué hace `scrape_origin` |
|---|---|---|
| **`none`** (default) | El cliente no nos dio nada del back | Scraping HTTP público + BFS por links del HTML. Limitado a páginas enlazadas desde el menú. |
| **`api`** | El cliente nos dio API key (Wix REST v3 o Webflow API v2) | Adapter llama a la API oficial para obtener la lista canónica de URLs. **Mejor cobertura**: incluye páginas no enlazadas. Si la API falla → fallback automático al modo `none`. |
| **`full`** | (Reservado) Acceso admin completo al panel del builder | Hoy se trata como `api`. Preparado para futuros adapters que necesiten más permisos (Wix Editor API privada, etc.). |

El modo se establece en el wizard (paso 1, panel opcional "credenciales del
back") o vía `PUT /api/v1/projects/{id}/source-credentials` después.

### 4.2 Decisión: ¿qué hace `scrape_origin` exactamente?

Pseudocódigo del agente:

```python
def run(ctx):
    project = ...
    seed_urls = self._seed_from_api(project)   # ← decisión aquí
    to_visit = [project.source_url, *seed_urls]
    visited = set()
    results = []

    while to_visit and len(results) < max_pages(50):
        url = to_visit.pop(0)
        if url in visited: continue
        html = httpx.get(url)               # mismo fetch para ambos modos
        results.append(persist_scraped_page(url, html))
        # encuentra más links del HTML para seguir
        for link in soup.find_all("a", href=True):
            if same_host and not visited: to_visit.append(link)

    session.add_all(results)
```

La diferencia entre los modos está **solo en `_seed_from_api`** — el resto del
crawler es idéntico:

```python
def _seed_from_api(project):
    if project.source_access_mode != "api":
        return []                            # modo none → BFS desde source_url solo
    if not project.source_credentials_encrypted:
        return []
    try:
        creds = decrypt_source_credentials(...)
    except CredentialsDecryptError:
        return []                            # FERNET_KEY rotada → fallback silencioso

    builder = project.builder_source.value
    try:
        return asyncio.run(self._fetch_api_urls(builder, creds))
    except (WixApiError, WebflowApiError):
        return []                            # API falla → fallback silencioso
```

Es decir: el adapter API **complementa**, no sustituye. Las URLs canónicas se
prepend al BFS, pero el crawler sigue buscando enlaces internos en cada página
visitada. Esto da la máxima cobertura sin ser exclusivo de la API.

### 4.3 Lo que hace cada adapter

Ambos son async, context manager, errores tipados:

#### `WixApiClient` (REST v3 Wix Headless)

```python
async with WixApiClient(api_key=..., site_id=...) as client:
    pages = await client.list_page_urls()
    # → [WixPageInfo(page_id, url, title, is_homepage), ...]
```

Bajo el capó:

1. `GET /site-properties/v4/properties` → resuelve dominio canónico (premium o
   subdomain wixsite).
2. `GET /site-pages/v1/pages?paging.limit=100` → lista todas las páginas.
3. Construye URLs `https://{dominio}/{pageUriSEO}` (homepage = `/`).

Errores tipados (caller decide qué hacer):

- `WixApiAuthError` (401/403)
- `WixApiNotFoundError` (404 — site_id incorrecto)
- `WixApiRateLimitError` (429)
- `WixApiError` (otros 5xx)

#### `WebflowApiClient` (Sites API v2)

Espejo del Wix:

```python
async with WebflowApiClient(api_token=..., site_id=...) as client:
    pages = await client.list_page_urls()
```

Bajo el capó:

1. `GET /sites/{site_id}` → resuelve dominio (`customDomains[0]` o fallback
   `defaultDomain`).
2. `GET /sites/{site_id}/pages` → lista.

Mismos tipos de error con prefijo `Webflow`.

### 4.4 Si la API falla, ¿qué pasa?

Cualquier excepción dentro de `_fetch_api_urls` (auth, network, rate-limit,
5xx) → el agente captura, loguea un warning con
`log.warning("scraper_origin_api_failed_fallback", ...)` y devuelve `[]`. El
crawler procede en modo `none` desde `project.source_url`.

El operador ve el warning en el `output_summary` de la fase y en logs
structlog. La fase **no falla** por una API caída — degrada elegantemente.

### 4.5 Qué se persiste

Independientemente del modo, cada página crawled se persiste como una fila
`ScrapedPage`:

| Campo | Contenido |
|---|---|
| `url` | URL absoluta de la página |
| `slug` | path sin host (`/contacto` → `contacto`) |
| `title` | `<title>` del HTML |
| `lang` | `<html lang>` |
| `html_raw` | HTML completo recibido del fetch |
| `html_clean` | HTML sanitizado (sin scripts, comentarios, tracking) |
| `status` | SUCCESS / FAILED |
| `scraped_at` | timestamp UTC |

Las siguientes 14 fases del pipeline trabajan sobre estas filas — el resto del
flujo es **agnóstico al modo origen**. Esto es el invariante que permite que
añadir nuevos adapters (Hostinger API, Squarespace, etc. en el futuro) no toque
el resto del pipeline.

### 4.6 Lo que NO hace `scrape_origin`

Importante para entender los límites:

- **No respeta `robots.txt`** en migración (el cliente nos dio consentimiento —
  es su web). Sí lo respeta en **prospección** comercial (otro flujo distinto).
- **No descarga assets** (imágenes, fonts, videos). Eso lo hace
  `optimize_assets` en una fase posterior.
- **No extrae bloques semánticos**. Eso lo hace `extract_content` con
  BeautifulSoup + selectores por builder.
- **Cap de 50 páginas por defecto** (`max_pages`). Para sitios grandes, se
  ajustaría vía `ctx.extra` en futuras versiones.
- **Usa httpx hoy** (HTTP simple). Para webs Wix/Webflow muy hidratadas el
  HTML inicial es un esqueleto + bundle JS que httpx no ejecuta — los
  extractores no encuentran bloques y las páginas se generan vacías. Es un
  **fallo silencioso** del que el operador solo se entera al ver el destino.
  Hostinger AI (SSR) y WordPress funcionan bien con httpx.

> **Próximo cambio (ADR-040 — programado para v0.20.0+)**: `scrape_origin`
> pasará a usar **Playwright + Chromium para todas las webs** (sin branching
> por builder). Lo que ve el usuario en su navegador es lo que scrapeamos.
> Trade-off aceptado: tiempos del pipeline ×5-10 (migración 30 páginas
> ~3-5 min de scraping vs ~30s ahora). Requerirá instalar Playwright +
> Chromium en el worker (`playwright install-deps && playwright install
> chromium`).

---

## Paso 5 — Fases `extract_content` y `preserve_seo`

Las dos siguientes fases del pipeline (orden: 2 y 3 de las 15). Ambas trabajan
sobre `scraped_pages` ya persistido y producen tablas nuevas.

### 5.1 `extract_content` — del HTML a bloques semánticos

#### Cómo elige extractor

```python
def _pick_extractor(builder):
    if builder in {WIX, HOSTINGER_AI, WEBFLOW}:
        return get_extractor(builder)        # extractor especializado
    return WixExtractor()                    # fallback genérico
```

Los 3 extractores especializados viven en
`packages/scraper-core/src/wcm_scraper_core/extractors/{wix,webflow,hostinger}.py`.
Cada uno conoce los selectores característicos de su builder:

| Builder | Señal de bloques | Patrón |
|---|---|---|
| **Wix** | `[data-mesh-id]` + atributos `data-*` | Selectores semi-estables |
| **Webflow** | `[data-w-id]` + clases `w-*` | Componentes Webflow nombrados |
| **Hostinger AI** | `[data-block-type="hero|text|...|"]` | **Mapping casi 1:1** a nuestro `BlockType` |

Hostinger es el más fácil porque etiqueta cada sección semánticamente. Wix y
Webflow requieren más heurísticas.

#### Qué hace el agente

```python
def run(ctx):
    extractor = self._pick_extractor(project.builder_source)
    pages = select(ScrapedPage).where(status=SUCCESS, project_id=...)

    for page in pages:
        if not page.html_clean: continue
        result = extractor.extract(page.html_clean, page.url)
        # result.blocks = [ExtractedBlock(block_type, order_index, content_json, lang), ...]
        for block in result.blocks:
            session.add(ContentBlock(
                project_id=...,
                page_id=page.id,
                block_type=block.block_type,
                order_index=block.order_index,
                content_json=block.content_json,
                source=EXTRACTED,
            ))
```

Cada bloque es una fila en `content_blocks`. El `block_type` es un enum
canónico (`HERO`, `TEXT`, `HEADING`, `IMAGE`, `GALLERY`, `CTA`, `FORM`,
`TESTIMONIAL`, `PRICING`, `FAQ`, `VIDEO`, `DIVIDER`, `FOOTER`, `NAV`,
`UNKNOWN`). El `content_json` lleva los datos estructurados específicos:

```json
// HERO
{"headline": "Tu sonrisa, nuestra prioridad", "subheadline": "...", "cta_text": "Reservar", "cta_url": "/citas", "bg_image_url": "..."}

// PRICING
{"tiers": [{"name": "Limpieza", "price": "45€", "features": ["30 min", "Revisión"]}, ...]}

// FAQ
{"items": [{"q": "¿Cuál es el horario?", "a": "L-V 9-20h"}, ...]}

// FORM (v0.19.0 Hostinger mejorado)
{"fields": [{"type": "email", "name": "email", "label": "Email", "required": true}, ...], "notes": "Hostinger Form — recrear en Gravity Forms"}
```

#### Bloques `UNKNOWN`

Si el extractor no reconoce un patrón:

- Crea un `ContentBlock` con `block_type=UNKNOWN` + `notes` explicando qué
  encontró.
- El agente cuenta cuántos hay y los reporta como **warnings** en `AgentResult`.
- El `bricks-transpiler` posterior los marca como **tareas residuales**
  ("revisar manualmente este bloque").

#### Metadata adicional (v0.19.0 Hostinger)

Además de `blocks`, el `ExtractionResult` ahora trae 3 dicts estructurados
(solo Hostinger por ahora):

| Campo | Para qué se usa |
|---|---|
| `theme_colors: dict` | El `bricks-transpiler` los aplica a **Theme Styles globales** de Bricks → toda la web hereda la paleta. |
| `theme_fonts: dict` | Idem, tipografía heading/body. |
| `contact_info: dict` | El `forms-rebuilder` lo usa para sembrar el destinatario del email de notificación; el `checklist-generator` lo expone como residual ("verificar contacto"). |

Estos campos NO se persisten todavía en una tabla nueva — viven en memoria
durante el pipeline y se consumen por las fases siguientes. Decisión consciente:
si crece el uso, en v0.20.0+ se persistirán en `project_meta` o equivalente.

#### Output del agente

```
AgentResult(
  summary="30 páginas → 142 bloques (3 unknown)",
  outputs={"pages_processed": 30, "blocks_extracted": 142, "unknown_blocks": 3},
  warnings=["3 bloques sin clasificar — generarán tareas residuales"]
)
```

### 5.2 `preserve_seo` — capturar y mapear el SEO

Fase crítica para no perder tráfico tras migración. **Sin esto, Google reindexa
desde cero y el cliente pierde meses de posicionamiento**.

#### Qué extrae de cada `scraped_page`

| Categoría | Etiquetas | Persistencia |
|---|---|---|
| **Meta básico** | `<title>`, `<meta name="description">`, `<meta name="keywords">`, `<meta name="robots">` | Inline en cada `scraped_page` |
| **Open Graph** | `og:title`, `og:description`, `og:image`, `og:type`, `og:url` | `scraped_pages.dom_tree_json.seo.og` |
| **Twitter Cards** | `twitter:card`, `twitter:image`, etc. | Idem |
| **JSON-LD** | `<script type="application/ld+json">` (LocalBusiness, Organization, BreadcrumbList, FAQPage) | Idem |
| **Canonical** | `<link rel="canonical">` | Idem |
| **Hreflang** | `<link rel="alternate" hreflang="...">` | Idem |

#### Qué hace a nivel proyecto

- **`/sitemap.xml`** del origen → parsea y compara con las URLs realmente
  crawled. Detecta páginas en sitemap NO crawled (probable fallo del scraper) y
  páginas crawled NO en sitemap (probable página descubierta por BFS).
- **`/robots.txt`** del origen → lo preserva tal cual; el `wp-deployer` lo
  aplicará en el destino (`/robots.txt` redirige al de WP por defecto, pero el
  cliente puede tener reglas custom).
- **Mapa de redirecciones 301** → si `project.preserve_paths=true`, no hace
  falta (URLs destino = origen). Si `false` o algunas páginas tienen slug
  distinto, genera filas en `seo_redirects`:

```
seo_redirects:
  project_id | source_path        | target_path           | http_code | reason
  -----------|--------------------|-----------------------|-----------|------------------
  7          | /productos/sofa-x  | /tienda/sofa-x        | 301       | path normalized
  7          | /es/contact        | /contacto             | 301       | i18n collapsed
  7          | /old-blog-2019/... | /blog/...             | 301       | structure changed
```

El `wp-deployer` posterior inyecta estos redirects en el plugin **Redirection**
del WP destino vía `POST /wp-json/redirection/v1/redirect`.

#### Plan SEO recomendado (no solo 1:1)

El agente además **propone mejoras** según el análisis del SEO original,
persistidas como `ResidualTask` informativas:

- Páginas sin `meta description` → "completar description en X páginas".
- `<title>` > 60 chars o < 30 chars → "ajustar longitud title".
- Sin Open Graph image en homepage → "configurar OG image".
- Sin JSON-LD LocalBusiness en sitio corporativo → "añadir schema LocalBusiness".
- Hreflang inconsistente entre versiones idiomáticas → "revisar hreflang".

Estas residuales son **POST_GO_LIVE** (no bloqueantes) y aparecen en el
checklist PDF al final.

#### Output del agente

```
AgentResult(
  summary="30 páginas con meta + 12 redirects + 4 mejoras SEO propuestas",
  outputs={"pages_with_meta": 30, "redirects_created": 12, "improvements_suggested": 4}
)
```

### 5.3 Estado del pipeline tras estas 2 fases

Tras `scrape_origin` + `extract_content` + `preserve_seo`:

```
Tablas pobladas:
- scraped_pages   (HTML raw + clean por página)
- content_blocks  (bloques semánticos extraídos)
- seo_redirects   (mapeo 301 si cambian paths)
- residual_tasks  (mejoras SEO opcionales — pueden estar 0)

Próxima fase:
- optimize_assets → descarga imágenes/fonts/videos identificados,
                    los convierte a WebP, prepara para upload
```

El contenido del origen está completamente capturado y normalizado. El pipeline
ya tiene todo lo que necesita para "construir" el destino sin volver a tocar el
origen nunca más.

---

## Paso 6 — Fases preparatorias para Bricks (`optimize_assets`, `detect_multilang`, `transpile_bricks`)

Estas 3 fases (4, 5 y 6 del pipeline) toman lo extraído y producen el
**artefacto final que el WP destino recibirá**: assets optimizados + mapa de
idiomas + JSON nativo de Bricks Builder. Tras estas 3, todo lo que falta es
"vaciar el contenido en WP".

### 6.1 `optimize_assets` — assets listos para producción

**Lo que recolecta** (de `content_blocks` + `ExtractionResult`):

- **Imágenes**: URLs de hero `bg_image_url`, image `src`, gallery `image_urls`,
  fondos en CSS inline, OG images.
- **Fuentes**: URLs de `@font-face src: url(...)`, Google Fonts en `<link>`.
- **Videos**: `<video src>`, `<source>`, iframes YouTube/Vimeo.

**Procesamiento por asset** (en paralelo, hasta N=5 concurrentes):

1. **Descarga** con httpx + retries 3x con backoff.
2. **Verifica** que es lo que dice ser (Pillow para imágenes; magic bytes para
   videos).
3. **Optimiza imágenes**:
   - Convierte a **WebP** con `cwebp -q 85` (mantiene el original como fallback
     `.jpg`/`.png`).
   - Genera **4 tamaños responsive** estándar WordPress:
     - `thumbnail` 150×150 crop
     - `medium` 300px max-side
     - `large` 1024px max-side
     - `full` original size
   - Si la imagen original es < 1024px, no genera `large` (sería upsize).
4. **Sube** a uno de los dos destinos según `project.asset_storage`:
   - `r2` → Cloudflare R2 vía boto3 (env `R2_*`). URLs
     `https://cdn.webcafeina.com/projects/{id}/assets/{slug}.{ext}`.
   - `wp_local` → REST `POST /wp-json/wp/v2/media` (multipart) directamente al
     WP destino. URLs son del propio dominio destino.
5. **Persiste** en `assets`:

```
assets:
  id | project_id | source_url             | local_path            | r2_url                     | wp_media_id | mime_type   | width | height | size_bytes | status
  ---|-----------|------------------------|----------------------|----------------------------|-------------|-------------|-------|--------|------------|--------
  1  | 7         | https://wix.../hero.jpg| /tmp/cache/hero.webp | https://cdn.../hero.webp   | NULL        | image/webp  | 1920  | 1080   | 145821     | OPTIMIZED
  2  | 7         | https://wix.../logo.png| /tmp/cache/logo.webp | NULL                       | 142         | image/webp  | 400   | 80     | 18234      | UPLOADED
```

**Fonts no-Google**:

- Si la URL del font ES Google Fonts → registra solo la URL canónica. El WP
  destino la cargará desde `fonts.googleapis.com` (mismo CDN, sin
  re-uploadear).
- Si NO es Google → descarga el `.woff2`/`.woff`/`.ttf`, sube a R2/WP, genera
  `@font-face` necesario para incluir en el CSS del tema.

**Output**:

```
AgentResult(
  summary="84 assets descargados, 76 optimizados (WebP), 8 fallidos",
  outputs={
    "total_assets": 84, "optimized": 76, "failed": 8,
    "total_saved_bytes": 12450000  # ~12 MB ahorrados
  }
)
```

Esta fase es **`required=False`**: si todo falla, el pipeline sigue. Las
imágenes del HTML quedarán apuntando a URLs del origen (lo que es feo pero
funcional para QA visual inmediato). Cada asset fallido genera residual task.

### 6.2 `detect_multilang` — mapeo de idiomas

Fase rápida (no toca red, solo BD). Lee `scraped_pages` y agrega:

```python
langs_seen = defaultdict(int)
for page in scraped_pages:
    if page.lang:
        short = page.lang[:2].lower()    # "es-ES" → "es"
        langs_seen[short] += 1

langs_list = sorted(langs_seen, key=lambda l: -langs_seen[l])
primary_lang = langs_list[0]              # el más común
is_multilang = len(langs_list) > 1
```

**Persistencia**:

- `project.langs = ["es", "en", "fr"]`
- `project.primary_lang = "es"`
- `project.is_multilang = True` (solo si el operador no lo había seteado ya en
  el wizard)

**Correlación de páginas equivalentes** (heurística simple):

- Páginas en diferentes langs con slug paralelo (`/contacto` ↔ `/contact` ↔
  `/contact-us`) se agrupan vía heurística de similitud + posición en el
  sitemap.
- Esta correlación se usará después por `wpml-configurator` para crear las
  traducciones vinculadas (o documentar el mapping en residual si no hay WPML).

**Casos complejos** que NO resuelve automáticamente:

- Subdominios por idioma (`es.cliente.com` vs `en.cliente.com`).
- `hreflang` sin path prefix (necesita inspección manual del HTML).
- Sites donde idioma se decide por cookie/IP.

→ Esos generan residual task informativa para revisión manual.

**Output**:

```
AgentResult(
  summary="Detectados 3 idiomas: ['es', 'en', 'fr'], is_multilang=True, primary=es",
  outputs={"langs": ["es", "en", "fr"], "pages_per_lang": {"es": 18, "en": 9, "fr": 3}}
)
```

### 6.3 `transpile_bricks` — el cerebro del proyecto

**La fase más compleja del pipeline**. Convierte `content_blocks` (bloques
semánticos genéricos) en **JSON nativo de Bricks Builder** (estructura
específica que Bricks lee del post meta `_bricks_page_content_2`).

#### Concepto Bricks

Bricks Builder almacena la estructura visual de cada página como un **árbol de
elementos** serializado:

```json
[
  {
    "id": "abc12345",
    "name": "section",
    "settings": {"_background": {"color": {"hex": "#FFFFFF"}}, "_padding": {"top": "80px"}},
    "children": [
      {
        "id": "def67890",
        "name": "container",
        "settings": {"_width": "60%"},
        "children": [
          {"id": "ghi11111", "name": "heading", "settings": {"text": "Tu sonrisa", "tag": "h1"}},
          {"id": "jkl22222", "name": "text-basic", "settings": {"text": "..."}},
          {"id": "mno33333", "name": "button", "settings": {"text": "Reservar", "link": {"url": "/citas"}}}
        ]
      }
    ]
  }
]
```

Cada elemento tiene: `id` único, `name` (tipo de elemento Bricks ~80
disponibles), `settings` (props por breakpoint), `children` (anidamiento).

#### Mapping de bloques → elementos Bricks

| `BlockType` (nuestro) | Estructura Bricks generada |
|---|---|
| `HERO` | `section` con `_background.image` + `container` interno (heading h1 + text-basic + button) |
| `HEADING` | `heading` con `tag` mapeado (h1/h2/h3...) |
| `TEXT` | `text-basic` con HTML del párrafo |
| `IMAGE` | `image` con `_image.id` (referencia al asset uploaded en fase 4) + `alt` + `caption` |
| `GALLERY` | `image-gallery` con array de `_images[].id` |
| `CTA` | `section` + `container` + `button` con `link.url` y `style: primary` |
| `FORM` | `form` con `fields` mapeados a Bricks form fields, action stub para Gravity Forms |
| `TESTIMONIAL` | `testimonial` (elemento custom de Bricks si está disponible) o `quote-block` + `text` |
| `PRICING` | `container` 3-col con N `pricing-table` |
| `FAQ` | `accordion` con N `accordion-item` |
| `VIDEO` | `video` con source/embed URL |
| `NAV` | `nav-menu` con referencia al menu WP (generado por `wp-deployer`) |
| `FOOTER` | `section` con `_padding`, columnas, footer link list |
| `UNKNOWN` | `div` placeholder con HTML raw + **comment** señalando "revisar manualmente" |

#### Breakpoints

Bricks soporta 3 breakpoints out-of-the-box (`mobile`, `tablet`, `desktop`). El
transpiler genera `settings` por breakpoint cuando el origen tenía media queries
CSS que afectaban a ese elemento:

```json
"settings": {
  "_width": "60%",              // base (desktop)
  "_widthTablet": "80%",
  "_widthMobile": "100%"
}
```

#### Theme Styles globales

Aprovecha `result.theme_colors` + `result.theme_fonts` del `ExtractionResult`
(poblados en `extract_content` para Hostinger; otros builders aún en text-only).
Genera un objeto Theme Style único:

```json
{
  "colors": {"primary": "#1A3A2A", "secondary": "#F5E6C8", "accent": "#D4A547"},
  "typography": {
    "heading": {"font_family": "Playfair Display", "weight": "700"},
    "body": {"font_family": "Inter", "weight": "400"}
  },
  "buttons": {"primary": {...}, "secondary": {...}}
}
```

Este JSON se persiste en `project.theme_styles_origin` y se aplica como Theme
Style activo en el WP destino (via WP-CLI vía SSH en la fase `deploy_wp`).

#### Persistencia

Cada `scraped_page` produce una fila en `bricks_pages`:

```
bricks_pages:
  id | project_id | slug      | title     | bricks_json (JSONB)  | status   | wp_post_id | last_import_error
  ---|-----------|-----------|-----------|----------------------|----------|------------|------------------
  1  | 7         | home      | Inicio    | [{section, ...}]     | SUCCESS  | NULL       | NULL
  2  | 7         | contacto  | Contacto  | [{section, ...}]     | SUCCESS  | NULL       | NULL
  3  | 7         | tienda    | Tienda    | [{section, ...}]     | SUCCESS  | NULL       | NULL
```

El `wp_post_id` se rellena en la siguiente fase (`deploy_wp`) cuando WP
devuelve el ID del post creado.

#### Patrones no mapeables

Si el transpilador encuentra un bloque `UNKNOWN` o una estructura CSS que no
puede traducir limpiamente a Bricks (animaciones custom, layouts experimentales,
embeds raros) → registra en `bricks_pages.last_import_error` + genera
**residual task** "revisar manualmente este elemento en Bricks Builder".

#### Output

```
AgentResult(
  summary="30 páginas transpiled → 142 elementos Bricks (3 unknown documentados)",
  outputs={
    "pages_transpiled": 30, "total_elements": 142, "unknown_elements": 3,
    "theme_styles_generated": True, "breakpoints_used": ["mobile", "tablet", "desktop"]
  }
)
```

### 6.4 Estado del pipeline tras estas 3 fases

```
Tablas pobladas (acumulado):
- scraped_pages       (HTML del origen)
- content_blocks      (bloques semánticos genéricos)
- assets              (imágenes/fonts optimizados + subidos)
- seo_redirects       (mapeo 301)
- bricks_pages        (JSON Bricks listo para inyectar en WP)
- residual_tasks      (incremental — assets fallidos, unknowns, mejoras SEO)

Project enriquecido:
- project.langs, primary_lang, is_multilang
- project.theme_styles_origin (paleta + fonts del origen)

Próxima fase:
- deploy_wp → la primera que TOCA el WP destino
```

A partir de aquí dejamos de "preparar" y empezamos a "construir el destino". La
siguiente fase es el momento de verdad.

---

## Paso 7 — Fase `deploy_wp` (la primera que toca el WP destino)

Esta es la fase de mayor riesgo del pipeline. Hasta ahora todo era trabajo
local en BD. Aquí abrimos sesión contra el WP destino real del cliente y
empezamos a escribir páginas. Si algo va mal, hay que poder rollback (lo veremos
en el paso 10).

### 7.1 Dos canales de comunicación con WP

El agente usa **dos clientes en paralelo** con el WP destino, cada uno para lo
que mejor sabe hacer:

| Cliente | Cuándo | Por qué |
|---|---|---|
| **`WpRestClient`** (REST API) | Crear/actualizar páginas + uploadear media + upsert opciones | Idempotente por slug, manejo de errores limpio, autenticación con Application Password |
| **`WpCliSshClient`** (WP-CLI vía SSH) | Escribir el `bricks_json` como post meta `_bricks_page_content_2` | El JSON puede ser muy grande (>500KB para páginas complejas). REST falla con timeouts o `request entity too large`. WP-CLI lo escribe a archivo y hace `wp post meta update --format=json` directamente |

Ambos se abren como **async context manager** dentro de `asyncio.run()` (Celery
es sync, pero httpx + paramiko se usan en modo async dentro de la coroutine).

#### Configuración necesaria (env vars)

```bash
WP_DEFAULT_SITE_URL=https://migracion-cliente.webcafeina.com
WP_DEFAULT_REST_USER=admin
WP_DEFAULT_REST_APP_PASSWORD="abcd efgh ijkl ..."   # Application Password (no la del user)
WP_DEFAULT_HOST=192.168.1.10                         # mismo host del SSH
WP_DEFAULT_SSH_USER=cliente_user                    # cPanel user
WP_DEFAULT_SSH_PORT=22
WP_DEFAULT_SSH_KEY_PATH=~/.ssh/wcm_deploy_rsa
WP_PATH=/home/cliente_user/public_html
WP_DEFAULT_WPCLI_PATH=/usr/local/bin/wp
```

El preflight (paso 4) ya verificó que estas envs están y responden. Si llegamos
a `deploy_wp` es porque el WP estaba accesible hace minutos.

### 7.2 Lo que hace el agente, paso a paso

```python
def run(ctx):
    project = ctx.session.get(Project, project_id)
    wp_config = WpClientConfig.from_env()                 # carga las envs

    bricks_pages = select(BricksPage).where(
        project_id=..., status=SUCCESS
    )
    if not bricks_pages:
        return AgentResult("No hay bricks_pages listas para desplegar")

    deployed, failed = asyncio.run(
        self._deploy_all(wp_config, bricks_pages, ctx)
    )

    return AgentResult(
        summary=f"{deployed} páginas desplegadas, {failed} fallidas",
        outputs={"deployed": deployed, "failed": failed, "target": wp_config.site_url}
    )
```

Y `_deploy_all` itera **secuencialmente** (no paralelo — el WP destino es un
recurso compartido que mejor no martillar):

```python
async with WpRestClient(wp_config) as rest, WpCliSshClient(wp_config) as cli:
    for bp in bricks_pages:
        try:
            # 1. Upsert de la página WP por slug
            wp_page = await rest.upsert_page_by_slug({
                "slug": bp.slug,
                "title": bp.title,
                "status": "draft",        # publicación manual desde dashboard
                "content": ""              # Bricks NO usa post_content
            })
            wp_post_id = wp_page["id"]

            # 2. Escribir el bricks_json en post meta vía WP-CLI
            await cli.bricks_import_content(wp_post_id, bp.bricks_json)

            # 3. Persistir el wp_post_id para trazabilidad (rollback futuro)
            bp.wp_post_id = wp_post_id
            bp.last_import_error = None
            deployed += 1
        except Exception as e:
            bp.last_import_error = f"{type(e).__name__}: {e}"[:1000]
            failed += 1
            # No abortamos — seguimos con la siguiente página
```

### 7.3 La clave: idempotencia por slug

`upsert_page_by_slug` hace:

1. `GET /wp-json/wp/v2/pages?slug=contacto&per_page=1&status=any` → busca si
   existe.
2. Si existe → `POST /wp-json/wp/v2/pages/{id}` (update parcial — REST ignora
   props no enviadas).
3. Si no existe → `POST /wp-json/wp/v2/pages` (create).

Consecuencias prácticas:

- **Re-ejecutar `deploy_wp` no duplica páginas**. La segunda vez actualiza las
  mismas.
- Es lo que permite usar `Resume` cuando una página falla — las que ya salieron
  OK no se vuelven a tocar (técnicamente sí, pero el resultado es idéntico).
- Si el cliente edita una página en WP a mano y luego se vuelve a correr
  `deploy_wp`, **se sobrescribe** (perdemos la edición manual). Por eso
  publicamos en `draft` por defecto, no en `publish`.

### 7.4 Por qué `status: "draft"` y no `"publish"`

Decisión consciente (ADR-039). Razones:

- El operador o el cliente quieren **revisar** antes de publicar.
- En `draft`, las páginas no son indexables ni visibles públicamente — el
  visual diff (fase 11) y la QA (fase 12) las visitan vía preview link
  autenticado.
- Cambiar a `publish` es un paso explícito en el checklist final, tras revisar.

> **Próximo cambio (ADR-039 — programado para v0.20.0+)**: se añadirá botón
> "Publicar todo" en el dashboard + endpoint `POST /projects/{id}/publish` +
> CLI `wcm projects publish ID` que en una sola acción publica todas las
> páginas, productos y activa los forms. Hasta entonces, la publicación es
> manual via wp-admin (5-10 min de clicks por migración típica).

### 7.5 El truco de WP-CLI para meta grande

Por qué no inyectamos el `bricks_json` directamente en el POST REST:

- Bricks Builder registra `_bricks_page_content_2` como meta key con
  `show_in_rest=true`. **En teoría** REST debería aceptarla.
- En la práctica, JSONs grandes (>200KB) fallan con `Bad Request` o
  `Request entity too large` según el nginx/Apache del cliente.

WP-CLI vía SSH lo evita:

```python
async def bricks_import_content(self, post_id, bricks_json):
    # 1. Serializa el JSON a fichero temporal local
    tmp_path = f"/tmp/wcm_bricks_{post_id}.json"
    async with aiofiles.open(tmp_path, "w") as f:
        await f.write(json.dumps(bricks_json))

    # 2. Sube por SFTP al servidor destino
    remote_tmp = f"/tmp/wcm_bricks_{post_id}.json"
    await self._sftp_put(tmp_path, remote_tmp)

    # 3. Ejecuta WP-CLI dentro del wp_path
    cmd = (
        f"{wp_config.wpcli_path} post meta update {post_id} "
        f"_bricks_page_content_2 --format=json "
        f"--path={wp_config.wp_path} --user=admin "
        f"< {remote_tmp}"
    )
    result = await self._ssh_exec(cmd, timeout=120)
    if result.returncode != 0:
        raise WpDeployerError(f"WP-CLI failed: {result.stderr}")

    # 4. Cleanup
    await self._ssh_exec(f"rm {remote_tmp}", timeout=5)
```

Es robusto pero requiere acceso SSH + WP-CLI instalado. Si el cliente no tiene
SSH (caso raro en cPanel decente), hay fallback REST con chunking — fuera de
scope hoy.

### 7.6 Qué se persiste

| Tabla | Cambio |
|---|---|
| `bricks_pages` | `wp_post_id` se rellena (era NULL); `last_import_error` queda NULL si éxito |
| `project_phases` | Fila `deploy_wp` pasa a COMPLETED (o FAILED si todas fallaron) |

El `wp_post_id` es lo que permite el **rollback** posterior (paso 10): el
agente `RollbackAgent` itera `bricks_pages WHERE wp_post_id IS NOT NULL` y hace
`DELETE /wp/v2/pages/{id}?force=true`.

### 7.7 Manejo de errores por página

El bucle es defensivo:

- Si una página individual falla (timeout, 5xx, WP-CLI exit ≠ 0, conflicto de
  slug) → registra el error en `bricks_pages.last_import_error`, incrementa
  `failed`, **sigue con la siguiente**.
- Si el agente termina con `failed > 0`, el `AgentResult` lo reporta pero la
  fase no marca FAILED a nivel pipeline. Es decisión del operador revisar las
  residuales y decidir si re-ejecutar.

Si el WP destino se cae **completamente** a mitad del deploy:

- El siguiente upsert lanza `WpRestError` → captura en el `try` por-página →
  registra error.
- **Todas las siguientes también fallarán** con error similar.
- El `AgentResult` reporta `deployed=3, failed=27` → el operador ve el patrón
  "todas a partir de la 4 fallan = caída del destino".

### 7.8 Qué NO hace `deploy_wp`

- **No instala plugins**. Asume que Bricks Builder está activo (preflight lo
  verificó). WooCommerce, Gravity Forms, WPML se asumen instalados manualmente
  por el operador o el cliente (warnings del preflight lo dicen).
- **No migra usuarios** del WP origen al destino (esto NO aplica para
  Wix/Webflow/Hostinger — no hay usuarios que migrar).
- **No configura tema padre/hijo** — asume que Bricks está activo como tema.
- **No toca menús nav** todavía — eso es parte de `nav-menu` element dentro del
  bricks_json. WP genera los nav menus al importar los elementos.
- **No invalida cache** del destino (LiteSpeed, WP Rocket, etc.) — eso es
  residual task para el operador.

### 7.9 Estado del pipeline tras esta fase

```
WP destino tiene:
- N páginas en status=draft con bricks_json en _bricks_page_content_2 meta
- Theme Styles aplicados (color paleta + fuentes del origen)
- Media library con las imágenes optimizadas (si asset_storage=wp_local)
- Sin nav menus visibles (se generan al publicar)
- Sin redirects 301 todavía (los aplica una sub-fase posterior)

bricks_pages todas con wp_post_id NOT NULL (excepto las que fallaron).

Próximas fases (todas required=False, condicionales):
- migrate_woo       (si has_ecommerce)
- configure_wpml    (si is_multilang)
- rebuild_forms     (siempre — detecta y salta si no hay forms)
```

A partir de aquí, las 4 fases siguientes son **opcionales** y especializadas.

---

## Paso 8 — Fases condicionales y verificación visual (`migrate_woo`, `configure_wpml`, `rebuild_forms`, `visual_diff`)

Las 4 fases tras `deploy_wp` (8 a 11 del pipeline). Todas son `required=False` —
si fallan, el pipeline continúa. Tres son condicionales según features del
proyecto; una corre siempre.

### 8.1 `migrate_woo` — productos a WooCommerce

**Cuándo corre**: solo si `project.has_ecommerce=True`.

#### Auto-detección de WooCommerce en destino

```python
async def _woocommerce_available(rest):
    try:
        await rest._request("GET", "/wc/v3/system_status/tools")
        return True
    except WpRestError as e:
        if e.status_code in (401, 403, 404):
            return False
        raise   # 5xx → propaga
```

3 escenarios posibles:

| Escenario | Resultado |
|---|---|
| WC instalado + responde 200 | sigue con la migración |
| WC NO instalado (404) | ResidualTask BLOCKING "Instalar y activar WooCommerce" → fase SKIPPED |
| `woo_products` vacío (scraper no extrajo productos) | ResidualTask CLIENT_CONFIG "Migrar productos manualmente" → fase SKIPPED |

#### Migración real (cuando WC + productos)

```python
for prod in woo_products:
    try:
        cat_ids = await _ensure_categories(rest, prod.categories, cache)  # upsert por slug
        wp_id = await _upsert_product(rest, prod, cat_ids)                # upsert por SKU
        prod.wp_product_id = wp_id
        migrated += 1
    except Exception as e:
        failed += 1
        warnings.append(f"Producto SKU={prod.sku!r} falló")
```

- **Categorías**: cache local en `dict[slug, wp_id]` para no llamar API por
  cada producto. Idempotente vía `GET /wc/v3/products/categories?slug=X` antes
  del POST.
- **Productos**: idempotente por SKU. `GET ?sku=X` → si existe
  `PUT /products/{id}`, si no `POST /products`. Status `draft` por defecto.

#### Pasarela de pago — SIEMPRE residual

Decisión consciente: la pasarela (Stripe, Redsys, PayPal, transferencia)
**nunca se migra automáticamente**. Requiere credenciales del cliente y
proveedor distinto al origen típico (Wix Payments → Stripe local). Tras
cualquier ejecución exitosa de WC, se crea:

```
ResidualTask(
  title="Configurar pasarela de pago en WooCommerce",
  category=BLOCKING_GO_LIVE,
  estimated_minutes=45
)
```

#### Lo que NO migra (hoy)

- **Historial de pedidos**: decisión MVP. Si el cliente lo necesita, hay
  residual task con instrucciones de exportar/importar manualmente.
- **Cupones**: idem.
- **Métodos de envío**: el operador los configura desde WC settings.

> **Próximos cambios (ADR-045 — programado para v0.20.0+)**:
>
> - **Historial de pedidos**: SÍ se migrará automáticamente si el proyecto
>   tiene credenciales del back (`source_access_mode='api'`). Nueva tabla
>   `woo_orders` con PII cifrada (Fernet) + borrado programado tras 30 días
>   (RGPD). Sin credenciales API → residual manual como hoy.
> - **Cupones**: NO se crean automáticamente en WC, pero la residual mostrará
>   la lista detectada en el origen (código, descuento, condiciones) para que
>   el operador decida recrearlos.
> - **Métodos de envío y pasarela de pago**: SIN cambios. Manual como hoy.
>
> Requiere cláusula RGPD nueva en el contrato cliente↔Webcafeína (acción
> humana, ver `docs/playbook-operativo.md` cuando se implemente).

#### Output

```
"Project 7: 12 productos migrados, 1 fallido. Pasarela de pago: residual obligatoria."
```

### 8.2 `configure_wpml` — sin licencia, siempre manual

**Cuándo corre**: solo si `project.is_multilang=True`.

#### La decisión arquitectónica (ADR-038)

Webcafeína **no tiene licencia WPML**. El agente NUNCA instala ni configura
nada en el destino. Su único trabajo es generar una `ResidualTask` muy
detallada para el operador.

> **Revisión planificada (ADR-038)**: cuando Webcafeína acumule ≥3 proyectos
> multilang completados al año, se abrirá ADR-04X para evaluar implementar
> `wpml-configurator` real (comprar licencia $99/año + ~5-7 días de desarrollo).
> Hasta entonces, la fase es manual y la residual contiene la guía paso a paso
> completa.

```
ResidualTask(
  title="Configurar WPML manualmente (3 idiomas)",
  category=BLOCKING_GO_LIVE,
  estimated_minutes=30 + 5 * total_secondary_pages,
  description="<guía Markdown de 100+ líneas>"
)
```

#### Qué contiene la guía generada

- Contexto detectado (cliente, target, idioma principal, idiomas totales).
- 6 pasos de configuración WPML: adquirir licencia (~$99/año) → subir plugins
  (core + String + Translation + Media) → activar → configurar idiomas +
  switcher → crear traducciones.
- **Lista exhaustiva de páginas por idioma** (cap 50 por idioma):

```markdown
### Idioma `en` (10 páginas)
- `home` ← https://origen.com/en/
- `about` ← https://origen.com/en/about
- `contact` ← https://origen.com/en/contact
...
```

- Validación final: switcher visible, hreflang en `<head>`, sitemap.xml
  multi-idioma.

Esto deja al operador con un checklist accionable sin tener que volver al
origen a contar páginas.

#### Si `is_multilang=False`

La fase salta limpia (devuelve summary "is_multilang=False, fase saltada") sin
crear nada.

### 8.3 `rebuild_forms` — siempre intenta detectar

**Cuándo corre**: siempre (sin `condition_attr`). Pero salta si no hay forms.

#### Detección de forms (en origen)

```python
detected = _detect_forms(pages)   # parsea html_raw con BeautifulSoup4
```

`_detect_forms`:

- Itera `scraped_pages.html_raw`.
- Busca todos los `<form>` con campos.
- **Dedupe por título normalizado** (mismo form en 5 páginas → solo cuenta 1).
- Por cada form extrae fields canónicos
  `[{type, name, label, required}]`:
  - **Estructurado**: si Hostinger marca `data-role="form-field"` +
    `data-field-type`, mapeo directo.
  - **Fallback**: si no hay data-role, infiere desde
    `<input type="X" name="Y">` + `<label for="Y">` del DOM.

Mapeo HTML5 → Gravity Forms:

| HTML5 | GF type |
|---|---|
| `text`, `search`, `password`, `hidden` | `text`/idem |
| `email` | `email` |
| `tel`, `phone` | `phone` |
| `url` | `website` |
| `number` | `number` |
| `date`, `datetime-local`, `time` | `date`/`time` |
| `file` | `fileupload` |
| `textarea` | `textarea` |
| `select` | `select` (con choices del DOM) |

#### Decisión por escenario

| Escenario | Resultado |
|---|---|
| 0 forms detectados | Fase salta sin tocar destino. Caso típico web corporativa sin contacto |
| ≥1 form detectado + Gravity Forms NO responde en `/wp-json/gf/v2/forms` | ResidualTask BLOCKING "Instalar y activar Gravity Forms" → fase SKIPPED |
| ≥1 form + GF disponible | Lista forms existentes (dedupe por título), crea los nuevos como `is_active: "0"` |

#### Si GF disponible y crea forms

Cada form se crea con:

```python
payload = {
    "title": form.title,
    "description": f"Migrado desde {form.source_url}",
    "button": {"type": "text", "text": "Enviar"},
    "fields": form.fields,
    "is_active": "0",                # creado inactivo para revisión
    "notifications": {
        "1": {
            "name": "Notificación admin (migrado)",
            "event": "form_submission",
            "to": notify_email,        # WP_DEFAULT_NOTIFY_EMAIL > COMPANY_CONTACT_EMAIL > info@webcafeina.com
            "subject": f"Nuevo envío: {form.title}",
            "message": "{all_fields}",
            "fromName": "Web",
            "from": "{admin_email}",
            "isActive": True
        }
    }
}
await rest._request("POST", "/gf/v2/forms", json=payload)
```

Tras crear → ResidualTask CLIENT_CONFIG con instrucciones de:

- Activar cada form (Formularios → Configuración → Estado).
- Insertarlos en las páginas finales con `[gravityform id=N]` o el bloque
  Bricks.
- Configurar integraciones manualmente (Mailchimp, CRM, Slack) — no se migran.

#### NO migra

- **Historial de envíos** del origen (decisión MVP).

### 8.4 `visual_diff` — comparar origen vs destino

La primera fase que **verifica el trabajo hecho** comparando lo que ve un
visitante en origen vs lo que ve en destino, página por página.

#### Cómo funciona

```python
def run(ctx):
    pages_to_compare = scraped_pages_success

    with screenshot_session() as session:           # 1 browser + 1 context reusados
        for page in pages_to_compare:
            try:
                source_url = page.url
                target_url = f"https://{project.target_domain}/{page.slug}"

                source_png = session.capture(source_url, viewport=1280)
                target_png = session.capture(target_url, viewport=1280)

                result = compare(source_png, target_png)
                # → VisualCompareResult(score, mismatched_pixels, overlay_png, width, height)

                # Upload a R2 o file:// fallback
                source_url_r2 = r2.put_bytes(f"projects/{id}/visual-diff/{slug}/source.png", source_png)
                target_url_r2 = r2.put_bytes(f"projects/{id}/visual-diff/{slug}/target.png", target_png)
                overlay_url_r2 = r2.put_bytes(f"projects/{id}/visual-diff/{slug}/overlay.png", result.overlay_png)

                # UPSERT en visual_diffs (por project_id + page_path)
                pg_insert(VisualDiff).values(
                    project_id=..., page_path=page.slug,
                    source_screenshot_url=source_url_r2,
                    target_screenshot_url=target_url_r2,
                    overlay_url=overlay_url_r2,
                    score=result.score,
                    viewport_width=1280
                ).on_conflict_do_update(...)
            except Exception:
                continue   # falla individual no para el resto

    # Recalcular score medio del proyecto
    project.visual_diff_avg_score = avg(scores)
```

#### El comparador

`pixelmatch` con threshold 0.15 (relativamente laxo para anti-aliasing).
Devuelve:

| Campo | Tipo |
|---|---|
| `score` | float 0-1 (1 = idénticos, 0 = nada en común) |
| `mismatched_pixels` | int |
| `total_pixels` | int |
| `overlay_png` | bytes — PNG con las zonas divergentes en rojo |
| `width`, `height` | dimensiones |

Score se calcula `1 - (mismatched_pixels / total_pixels)`.

#### Resiliencia

- **Playwright no instalado** en el worker → la fase salta limpia con warning.
  Genera ResidualTask "instalar Playwright + chromium".
- **R2 no configurado** → URLs `file:///tmp/wcm-visual-diff/...` locales (el
  dashboard mostrará "(local)" en los thumbnails, pero el score se calcula
  igual).
- **Página individual falla** (target no responde, redirect raro) → continúa
  con las siguientes, registra warning.

#### Qué ve el operador después

En `/projects/[id]/diff`:

- Tabla con una fila por página: thumbnail origen (mini) | thumbnail destino
  (mini) | thumbnail overlay (mini con rojo) | ScoreBadge (verde ≥85%, ámbar
  70-85%, rojo <70%).
- Click en cualquier thumbnail abre modal full-size con las 3 imágenes lado a
  lado.
- En el header del proyecto: `visual_diff_avg_score` aparece como pill
  (ej. "diff medio 91%").

#### Output

```
"Project 7: 28 páginas comparadas, avg score 0.91 (3 con score <70%)"
```

Las páginas con score <70% no generan residual automática — el operador decide
visualmente si las diferencias son aceptables. Si quiere bloqueante, lo
configura via threshold global (env `VISUAL_DIFF_THRESHOLD`).

> **Próximo cambio (ADR-044 — programado para v0.20.0+)**: el agente generará
> ResidualTask VISUAL_CONTENT automática para cada página con score < umbral.
> Umbral configurable por proyecto vía `projects.visual_diff_threshold` (col
> nueva Alembic 0010, default NULL = usa env global `VISUAL_DIFF_RESIDUAL_THRESHOLD`,
> default global 0.70). UI nueva sección "Configuración avanzada" en
> `/projects/[id]` para ajustar por cliente (piloto interno ≥0.50, cliente
> corporativo ≥0.90). CLI `wcm projects set-visual-threshold ID --value X`.
> La fase sigue siendo `required=False` — la residual no bloquea, solo asegura
> que el operador no olvide revisar las páginas críticas.

### 8.5 Estado del pipeline tras estas 4 fases

```
WP destino tiene:
- N páginas Bricks en draft (todas las del origen)
- Theme Styles aplicados
- Media library con imágenes optimizadas
- Productos WooCommerce (si has_ecommerce) en draft
- Forms Gravity creados como inactive (si rebuild_forms encontró)
- WPML aún sin tocar (residual manual)

visual_diffs tabla con N filas (una por página comparada).
project.visual_diff_avg_score poblado.

Residual tasks generadas (suma de las 4 fases):
- "Configurar pasarela de pago" (BLOCKING)
- "Configurar WPML manualmente" (si is_multilang)
- "Revisar X formularios Gravity Forms" (si forms creados)
- "Instalar WooCommerce/Gravity Forms" (si faltaban)

Próximas fases (3 últimas):
- qa                     → batería QA automática
- generate_checklist     → PDF entregable
- sync_clickup + notify  → operador avisado
```

A partir de aquí el trabajo en WP está hecho. Las 3 últimas fases son
**observabilidad y entrega**: dejar la documentación clara para que el operador
pueda revisar y entregar al cliente.

---

## Paso 9 — Las 3 últimas fases: QA, entregable y cierre (`qa`, `generate_checklist`, `sync_clickup`+`notify`)

Las fases 12, 13, 14 y 15 del pipeline. Todo el trabajo en WP ya está hecho.
Estas son **observabilidad + documentación + cierre**: validar la calidad de lo
construido, generar el entregable para el cliente y avisar al operador.

### 9.1 `qa` — batería de QA automática

Verifica 6 cosas sobre el WP destino. Ejecuta en paralelo con
`asyncio.gather`. Persiste el resultado en `qa_reports` (histórico, no UPSERT —
cada ejecución una fila).

| Check | Herramienta | Bloqueante | Genera residual si... |
|---|---|---|---|
| **Lighthouse desktop + mobile** | `lighthouse` CLI Node | no | perf < 50 |
| **HTML W3C** | `validator.w3.org/nu/?out=json` | no | errors > 20 |
| **Links rotos** | httpx + bs4 (HEAD primero, GET ranged si 405) | no | broken > 5 |
| **HTTPS válido** | `httpx.get(target, verify=True)` | no | inválido |
| **`robots.txt` accesible** | GET `target/robots.txt` | no | 4xx/5xx |
| **`sitemap.xml` accesible** | GET `target/sitemap.xml` o `sitemap_index.xml` | no | 4xx/5xx |

#### Detalles relevantes por check

**Lighthouse**: subprocess Node con
`lighthouse target --output=json --form-factor=desktop|mobile --chrome-flags="--headless"`.
Captura `performance`, `accessibility`, `best_practices`, `seo` (cada uno
0-100). Si Lighthouse no está instalado en el worker → fase devuelve
`lighthouse_skipped=true` + residual
"instalar `npm install -g lighthouse@^12`".

**W3C validator**: hasta 50 páginas (cap por rate-limit 1.2s/req). Throttle
interno. Si la API W3C cae → la fase no rompe, errors_count=0 con warning en
summary.

**Link checker**: itera todas las páginas `bricks_pages.wp_post_id NOT NULL`.
Para cada una, parsea HTML con bs4, extrae `<a href>`, deduplica por URL. Para
cada link **del propio dominio** (no externos):

1. HEAD primero — barato.
2. Si HEAD devuelve 405 (Method Not Allowed, frecuente en algunos servers) →
   GET con `Range: bytes=0-0`.
3. Si 4xx/5xx →
   `BrokenLink(url, status_code, error, source_pages: [donde apareció])`.

Devuelve `LinkReport(total_checked, broken_count, broken: list[BrokenLink])`.

**HTTPS check**: simple `httpx.get(target, verify=True)`. Si falla SSL →
`https_valid=False`.

**robots.txt + sitemap.xml**: simple `httpx.get` con timeout 10s. True si
responde 200.

#### Persistencia

`QaReport` (una fila por ejecución del agente, histórico no UPSERT):

```
qa_reports:
  id | project_id | lighthouse_perf_desktop | lighthouse_perf_mobile | lighthouse_a11y_avg | ...
                                                                                                |
  ...html_validator_errors_count | broken_links_count | total_links_checked | https_valid | robots_accessible | sitemap_accessible | report_json (JSONB) | created_at
```

#### Residual tasks generadas por fallos críticos

| Trigger | Categoría | Estimación |
|---|---|---|
| `lighthouse_skipped=True` | CLIENT_CONFIG | 15 min |
| `lh_desktop.performance < 50` | POST_GO_LIVE | 30 min |
| `lh_mobile.performance < 50` | POST_GO_LIVE | 30 min |
| `html_errors > 20` | POST_GO_LIVE | 30 min |
| `broken_links > 5` | BLOCKING_GO_LIVE | 30 min |
| `https_valid=False` | BLOCKING_GO_LIVE | 30 min |
| `robots_accessible=False` | CLIENT_CONFIG | 15 min |
| `sitemap_accessible=False` | CLIENT_CONFIG | 15 min |

#### Status del proyecto tras `qa`

- Si **algún** check bloqueante falla → la fase termina FAILED, lo que vimos en
  paso 3 lleva a `project.status=QA_FAILED` (porque `required=False` permite
  continuar el pipeline, pero el `failed_phase` queda marcado).
- Si todo OK pero hay residuales POST_GO_LIVE → fase COMPLETED, el proyecto
  continúa hacia COMPLETED.
- Decisión: la fase NO falla por scores bajos — solo si el target es
  completamente inaccesible. Los residuales quedan en el checklist para que el
  operador decida.

#### Lo que ve el operador en `/projects/[id]/qa`

`<QaScorecards>`:

- 5 ScoreCards Lighthouse (verde ≥80, ámbar 50-79, rojo <50): perf desktop /
  perf mobile / a11y / best-practices / SEO.
- 2 CountCards HTML W3C: errores / warnings.
- 2 CountCards links: rotos / total checked.
- 3 BoolCards SEO/SSL: HTTPS / robots.txt / sitemap.xml.
- Tabla detallada de **broken links** (cap 50) con URL + status + páginas
  donde aparece.

### 9.2 `generate_checklist` — el entregable PDF + MD

Genera el documento que se envía al cliente o queda como referencia interna del
operador. Markdown + PDF con paleta Webcafeína.

#### Cómo funciona

```python
def run(ctx):
    project = ...
    residuals = select(ResidualTask).where(project_id=...).order_by(category, id)

    md_text = self._render_markdown(project, residuals)        # Jinja2 template
    html_body = render_markdown_to_html(md_text)               # markdown-it-py
    css = self._load_css()                                     # checklist.css con paleta
    full_html = self._wrap_html(html_body)

    pdf_bytes = render_pdf(full_html, css)                     # WeasyPrint

    md_url, pdf_url = self._upload_two(r2, project_id, md_bytes, pdf_bytes)
    project.checklist_md_url = md_url
    project.checklist_pdf_url = pdf_url
```

#### Categorías canónicas (orden en el PDF)

| Categoría | Severidad | Posición |
|---|---|---|
| `BLOCKING_GO_LIVE` | Crítica | Primera — destacada en rojo |
| `CLIENT_CONFIG` | Pendiente del cliente | Segunda |
| `VISUAL_CONTENT` | Revisión visual recomendada | Tercera |
| `POST_GO_LIVE` | Mejoras opcionales | Cuarta |
| `OTHER` | Catch-all | Última |

#### Estructura del PDF

1. **Header**: Cliente · Project ID · Target domain · Fecha generación ·
   Status proyecto.
2. **Tabla resumen**: counts por status (open / in_progress / blocked / skipped
   / done) + total horas estimadas (suma de `estimated_minutes` de abiertas).
3. **Sección por categoría** (las que tengan tareas):
   - Título de categoría.
   - Descripción ("Estas tareas DEBEN resolverse antes de entregar el sitio al
     cliente.").
   - Lista de tareas con título + descripción + status pill + tiempo estimado +
     generated_by + assignee.
4. **Footer**: bloque legal Webcafeína (CIF, dirección, contacto, web).

#### Storage

- **R2 configurado** (env `R2_*` con boto3 compat): paths
  `projects/{id}/checklist/{checklist.md,checklist.pdf}`.
- **R2 no configurado** → fallback
  `file:///tmp/wcm-checklist/projects/{id}/...`. El endpoint
  `/api/v1/projects/{id}/checklist/download` detecta `file://` y hace stream
  local (con `Content-Disposition: attachment`).

#### Resiliencia con WeasyPrint

WeasyPrint requiere libs SO (libpango, libcairo). En macOS dev son brew install
fáciles, en Linux server son apt install.

- Si WeasyPrint NO está disponible o falla al renderizar → la fase devuelve
  **solo el MD** + warning + residual "instalar libs SO de WeasyPrint en el
  worker". El proyecto sigue siendo entregable (MD se puede leer en cualquier
  editor).
- Si MD también falla (Jinja2 explosion) → la fase marca FAILED. Pero el
  template usa `StrictUndefined` solo para pillar bugs en dev; en prod el
  contexto siempre está completo.

#### Sin residuales pendientes

Si todas las residuales están DONE o no hay ninguna, el checklist se genera con
header + tabla resumen "Sin tareas pendientes. La migración está lista para
entregar al cliente." Documenta el estado final.

#### Output

```
"Project 7: checklist generado · 14 tareas · PDF=OK · MD=OK"
```

### 9.3 `sync_clickup` + `notify` — cierre del ciclo

Las 2 últimas fases. Son utilidades operativas: avisar al operador y dejar las
residuales sincronizadas con ClickUp.

#### `sync_clickup`

Crea **una tarea principal** del proyecto en la lista ClickUp "Microtareas"
(id `900102088242`) + **subtareas** por cada `ResidualTask` del proyecto.

```python
def run(ctx):
    parent = clickup_create_task(
        list_id="900102088242",
        title=f"Migración {project.client_name}",
        description=f"Proyecto #{project.id} · {project.source_url} → {project.target_domain}",
        # No assignee — el equipo decide en ClickUp tras la creación
    )
    project.clickup_task_id = parent["id"]

    for residual in residuals:
        sub = clickup_create_subtask(
            parent_id=parent["id"],
            title=residual.title,
            description=residual.description,
            estimated_minutes=residual.estimated_minutes,
        )
        residual.clickup_task_id = sub["id"]
```

#### Sincronización bidireccional (webhook)

ClickUp tiene webhooks configurados para `taskStatusUpdated`. Cuando alguien
cierra la subtarea en ClickUp:

```
POST /api/v1/webhooks/clickup → busca ResidualTask por clickup_task_id → marca DONE en BD
```

Y al revés: cuando el operador cierra una residual desde el dashboard, llama
`clickup_update_task(status=closed)`.

#### Si ClickUp no responde

- Sin `CLICKUP_API_TOKEN` en `.env` → fase devuelve
  `{skipped: True, reason: "..."}` sin error.
- API caída/4xx → fase FAILED + warning. Residual task "sincronizar manualmente
  con ClickUp tras restablecer API".

#### `notify` — última fase

Envío de email al operador del equipo. Configurable vía env:

```bash
COMPANY_CONTACT_EMAIL=info@webcafeina.com    # destinatario default
```

El email contiene:

- Asunto: `Migración completada: {client_name} ({project.target_domain})`
- Resumen del pipeline: fases completed / failed / skipped.
- Counts de residuales por categoría.
- Visual diff avg score.
- QA Lighthouse highlights.
- Link al checklist PDF.
- Link al proyecto en el dashboard:
  `https://dashboard.webcafeina.com/projects/{id}`.

Usa Resend con API key en `RESEND_API_KEY`. Si no configurada → fase salta con
`{skipped: True}` (no rompe).

#### El operador NO recibe spam

`notify` se ejecuta UNA vez al final del pipeline. Para cambios intermedios
(fase failed a mitad), el dashboard ya está reactivo (SSE) — no necesita email.

### 9.4 Estado final del proyecto

```
project.status = COMPLETED  (o QA_FAILED si qa falló bloqueante)
project.completed_at = <timestamp>
project.checklist_md_url + checklist_pdf_url → poblados
project.visual_diff_avg_score → poblado
project.clickup_task_id → poblado (si ClickUp habilitado)

Tablas pobladas (acumulado total):
- scraped_pages
- content_blocks
- assets
- seo_redirects
- bricks_pages (todas con wp_post_id NOT NULL si todo OK)
- woo_products (si has_ecommerce)
- visual_diffs (N filas, una por página comparada)
- qa_reports (1 fila más por cada ejecución)
- residual_tasks (todas las generadas a lo largo del pipeline)
- project_phases (15 filas, una por fase)
- audit_log (entradas de cada cambio relevante)

Operador recibe:
- Email Resend con resumen + link al dashboard.
- Tarea ClickUp principal + N subtareas asignables.
- Visualmente en /projects/[id]: stepper completo, scorecards, checklist descargable.

WP destino tiene:
- Páginas en draft listas para revisión + publicación.
- Theme Styles aplicados.
- Media uploaded.
- Productos en draft (si ecom).
- Forms inactive (si rebuild_forms encontró).
- Redirects 301 plantilla aplicados (si paths cambiaron).
```

### 9.5 Lo que el operador hace después (no es parte del pipeline)

El pipeline termina, pero queda trabajo humano:

1. **Visual diff review** (15-30 min): abrir `/projects/[id]/diff`, validar
   páginas con score <85%, anotar diferencias aceptables vs no aceptables.
2. **Checklist** (variable): completar las residuales BLOCKING (instalar
   plugins, configurar pasarela, WPML).
3. **Publicar páginas** en WP destino: cambiar status `draft → publish` desde
   wp-admin o por bulk action.
4. **Verificación final** del cliente sobre dominio temporal.
5. **DNS cutover** (cuando cliente confirma): apuntar dominio definitivo al
   server.
6. **Cerrar proyecto en ClickUp** + email "go live" al cliente.

Si algo va mal en este post-pipeline humano, el operador tiene **rollback**
disponible (paso 10).

---

## Paso 10 — Rollback y modos de recuperación

El pipeline puede fallar a mitad. El operador puede cambiar de opinión tras un
deploy. El cliente puede pedir empezar de nuevo. Para todos estos casos existe
el rollback MVP (v0.19.0).

### 10.1 Cuándo se permite el rollback

El endpoint `POST /api/v1/projects/{id}/rollback` solo acepta proyectos en uno
de estos 3 estados:

| Status actual | Caso típico |
|---|---|
| `completed` | Deploy salió OK, pero el cliente o el operador deciden "no nos gusta, vamos a probar otra vez" |
| `qa_failed` | QA falló (alguna check bloqueante), preferimos empezar limpio antes de Resume |
| `blocked_human_input` | Una fase required se cayó, no quieres reintentar — quieres borrar lo creado y replantear |

Cualquier otro status devuelve **409 Conflict** con mensaje explicativo:

```
"Rollback solo permitido si status ∈ {qa_failed, completed, blocked_human_input}.
 Estado actual: running."
```

Razón: durante `running` el worker tiene la sesión SQLAlchemy abierta. Borrar
páginas en paralelo crearía race conditions.

### 10.2 Cómo se dispara

**UI**:

- Vas a `/projects/[id]` → en `<ProjectActions>` aparece botón "Rollback"
  (icon `Undo2`) si el status lo permite.
- Click → aparece confirmación inline en rojo: "¿Borrar las páginas WP?" +
  "Sí, deshacer" / "Cancelar".
- Confirmar → encola task + redirect al mismo proyecto (que ahora mostrará la
  fase `rollback` corriendo en el stepper).

**CLI**:

```bash
wcm projects rollback 7              # prompt interactivo
wcm projects rollback 7 --yes        # sin prompt (para scripts/CI)
```

**API directa**:

```bash
curl -X POST https://api.../api/v1/projects/7/rollback \
  -H "Authorization: Bearer ..." \
  -H "Content-Type: application/json" \
  -d '{"confirm": true}'
```

El body `{"confirm": true}` es obligatorio. Sin él → 409. Es protección contra
disparos accidentales por scripts mal configurados.

### 10.3 Lo que hace el `RollbackAgent`

Lectura inicial:

```python
pages = select(BricksPage).where(
    project_id=...,
    wp_post_id IS NOT NULL
)
```

Es decir, solo las páginas que `deploy_wp` consiguió crear (con `wp_post_id`
poblado). Las que fallaron en deploy nunca llegaron a WP, no hay que borrarlas.

Por cada página:

```python
async with WpRestClient(wp_config) as rest:
    for bp in pages:
        try:
            await rest.delete_page(bp.wp_post_id, force=True)   # DELETE /wp/v2/pages/{id}?force=true
            bp.wp_post_id = None                                # resetea para futuro re-deploy
            deleted += 1
        except Exception as e:
            failed += 1
            warnings.append(f"Página WP id={bp.wp_post_id} (slug={bp.slug}) falló")
            # NO atropella las siguientes
```

`force=true` salta la papelera de WP — borra definitivamente. Decisión
consciente: si quisiéramos recuperar páginas borradas a mano desde wp-admin,
eso es responsabilidad del operador (no del rollback automático).

Al terminar:

```python
project.status = ProjectStatus.ROLLED_BACK
project.completed_at = datetime.now(UTC)
```

`ROLLED_BACK` es un status terminal nuevo (v0.19.0). En `<ProjectActions>` el
proyecto se muestra como "proyecto revertido" — ya no permite Start ni Resume
directamente.

### 10.4 Lo que el rollback NO hace (importante)

| NO recupera | Razón | Workaround |
|---|---|---|
| **Cambios a páginas existentes pre-migración** | No las teníamos en snapshot, no sabemos qué había antes | Hacer backup WP destino antes del deploy (manual del operador) |
| **Cambios a menús nav** | Bricks los crea como side-effect de los `nav-menu` elements | Borrar manualmente desde Apariencia → Menús |
| **Cambios a opciones de WP** (Bricks Theme Styles, etc.) | Modificamos `option` rows, no las versionamos | Borrar manualmente desde Bricks → Settings |
| **Productos WooCommerce** | Tabla `wp_posts` distinta (`post_type=product`), no las toca el agent MVP | Borrar bulk desde wp-admin → Productos |
| **Forms Gravity Forms** | Tabla custom de GF, no es post type estándar | Borrar uno a uno desde Formularios |
| **Categorías WC, taxonomías** | Aplicado por `migrate_woo` indirectamente | Limpiar manualmente |
| **Media library** | Imágenes uploaded por `optimize_assets` siguen allí | `wp media regenerate` o borrar bulk |
| **Redirects 301** | Inyectados en el plugin Redirection | Borrar desde Tools → Redirection |

Decisión MVP: el rollback solo borra las **páginas** (que es el 90% del valor
en una migración típica web corporativa).

> **Próximo cambio (ADR-042 — programado para v0.20.0+)**: nueva fase
> `pre_deploy_snapshot` justo antes de `deploy_wp` que ejecuta `wp db export`
> vía SSH y persiste el path en `projects.pre_deploy_snapshot_path`. El
> `RollbackAgent` pasa a hacer `wp db import` (restore atómico) → recupera
> literalmente todo (páginas, productos, forms, menús, opciones, todo). Si
> no hay snapshot (proyectos pre-v0.20.0+), fallback al MVP actual. Trade-off:
> downtime ~10-60s del WP destino durante restore. Para piloto interno sin
> tráfico real es irrelevante; para producción se mostrará warning explícito.

### 10.5 Idempotencia

El rollback es idempotente: re-ejecutarlo tras un rollback parcial completa el
trabajo sin duplicar acciones.

**Escenario típico**: rollback de 30 páginas, 5 fallan por red intermitente.
`wp_post_id` queda None en las 25 OK, sigue poblado en las 5 fallidas.

- Reintentar rollback → solo procesa las 5 que aún tienen
  `wp_post_id NOT NULL`.
- Si todas borran OK la segunda vez → `pages_deleted=5, pages_failed=0`.

El operador puede ejecutar 3-4 veces hasta que pages_failed=0. Sin riesgo de
borrar la misma página dos veces (porque `wp_post_id` se resetea a None tras
éxito).

### 10.6 Re-deploy tras rollback

Tras rollback el proyecto queda en `ROLLED_BACK`. ¿Cómo vuelvo a desplegar?

**Hoy** (v0.19.0): el operador NO puede pulsar Start desde la UI directamente
(`ROLLED_BACK` es terminal). Workarounds:

1. **Crear un nuevo proyecto** desde el wizard apuntando al mismo origen +
   destino.
2. **Vía API directa**: `PATCH /api/v1/projects/{id}` con
   `{"status": "queued"}` y luego `POST /start`. Avanzado, requiere conocer el
   endpoint.

> **Próximo cambio (ADR-041 — programado para v0.20.0+)**: botón
> "Re-arrancar pipeline" en ProjectActions cuando status=`rolled_back`,
> endpoint `POST /api/v1/projects/{id}/restart` y CLI `wcm projects restart
> ID`. Resetea timestamps + vuelve a `queued` sin borrar historial (visual
> diffs, residuales, transpilado conservados). Cierra el ciclo de iteración
> en 1 click para casos típicos durante pilotos (ajustar config y re-deployar
> sin recrear proyecto duplicado).

### 10.7 Lo que el operador NO necesita hacer (rollback automático)

Tras un rollback exitoso, **el proyecto en BD sigue intacto**. NO se borran:

- `scraped_pages` (HTML del origen)
- `content_blocks` (bloques semánticos extraídos)
- `bricks_pages.bricks_json` (el JSON Bricks pre-deploy)
- `assets`, `seo_redirects`, `residual_tasks`, `visual_diffs`, `qa_reports`

Razón: el rollback NO es "borrar el proyecto", es "deshacer lo que llegó al WP
destino". El estado pre-deploy queda preservado para diagnóstico (¿qué
bricks_json se intentó deployar?) y para re-deploy futuro.

Para borrar el proyecto entero (BD + assets R2) hay un endpoint
`DELETE /api/v1/projects/{id}` separado, admin-only, con confirm explícito.

### 10.8 Los 3 caminos de recuperación según el problema

Cheatsheet de cuándo usar qué:

| Problema | Acción recomendada |
|---|---|
| **Una fase no required falló** (visual_diff timeout, qa lighthouse no instalado) | Nada — el pipeline llegó a COMPLETED con residuales. Revisar checklist |
| **Una fase required falló** (scrape_origin no encuentra páginas, deploy_wp pierde conexión) → status `blocked_human_input` | **Resume** desde botón UI. Mismo pipeline, re-ejecuta desde donde dejó (las COMPLETED son idempotentes) |
| **QA falló bloqueante** (broken links >5, HTTPS inválido) → status `qa_failed` | 1) Arreglar el problema en WP destino manualmente. 2) **Resume** (re-ejecuta qa). Si no se arregla → **Rollback** + crear proyecto nuevo |
| **Deploy salió OK pero el cliente cambió de opinión** | **Rollback** → empezar de nuevo con ajustes |
| **Configuración mal hecha** (credenciales WP equivocadas, builder mal detectado, features incorrectas) | **Rollback** (si llegó a deploy) + crear proyecto nuevo desde wizard con ajustes |
| **Proyecto entero un desastre, queremos borrar todo** | `DELETE /api/v1/projects/{id}` (admin) |

### 10.9 Lo que verás durante un rollback

El rollback es una task Celery más, así que **dispara eventos SSE** como el
pipeline normal:

```
publish_phase_event(project_id, "rollback", "running")
...
publish_phase_event(project_id, "rollback", "completed", summary="14 páginas borradas, 0 fallidas")
```

En el dashboard:

- `ProjectPoller` recibe el evento → `router.refresh()`.
- El stepper sigue mostrando las 15 fases originales (no añade un dot para
  rollback — es operación lateral).
- El status badge en `ProjectActions` cambia: pasa de `qa_failed` a `running`
  (durante el rollback) y luego a `rolled_back` (terminal).
- Toast Sonner: "Rollback encolado · task {task_id[:8]}…".

En CLI con `wcm projects watch ID`: el panel Rich muestra una nueva línea
"rollback · running" hasta que el status pasa a terminal.

---

## Resumen de los 10 pasos del flujo

```
1. Proyecto = unidad de migración (status queued → running → terminal)
2. Wizard /projects/new 4 pasos + preflight 4 chequeos antes del Start
3. Pipeline 15 fases en orden, una sesión SQLAlchemy, async dentro de Celery
4. Modo origen: none (scraping) vs api (Wix/Webflow adapter) con fallback
5. scrape_origin → extract_content → preserve_seo (capturar y normalizar)
6. optimize_assets → detect_multilang → transpile_bricks (preparar para WP)
7. deploy_wp (REST upsert + WP-CLI vía SSH para meta grande)
8. migrate_woo + configure_wpml + rebuild_forms + visual_diff (post-deploy)
9. qa + generate_checklist + sync_clickup + notify (cierre y entrega)
10. Rollback MVP: deshacer páginas creadas; no recupera cambios previos
```

---

## Notas para la primera prueba real

1. **WP destino real**: la migración no funciona contra `localhost` cualquiera —
   necesita un WP en WHM/cPanel con SSH habilitado, Bricks Builder licenciado y
   plugins (al menos Gravity Forms; WC si vas a probar ecom). Las env vars
   `WP_DEFAULT_*` deben apuntar a ese WP.

2. **Lead piloto pequeño**: para la primera prueba, elige un lead Wix
   corporativo de 5-10 páginas (sin tienda ni multilang). Eso te da un pipeline
   simple que recorre las fases típicas sin sorpresas.

3. **El primer Start tarda**: scraping + screenshots + Lighthouse + PDF render =
   típicamente 8-20 min para una web de 10 páginas. El SSE/polling te lo
   muestra en tiempo real.

4. **Esperar residuales**: incluso una migración "perfecta" genera 4-8
   residuales (pasarela de pago si has_ecommerce, configurar GF email
   destinatario, instalar libs SO del worker, etc.). Son normales — el
   checklist está pensado para eso.

---

## Mantenimiento de este documento

Cuando algo del flujo cambie:

- **Nueva fase**: añadirla a la lista `_DEFAULT_PHASES` documentada en el paso
  3 + crear paso nuevo o ampliar uno existente.
- **Fase eliminada**: tachar en paso 3 + retirar la sección correspondiente.
- **Cambio de status posible**: actualizar diagrama en paso 1.
- **Nuevo modo del origen**: añadir fila a la tabla del paso 4 + sección
  específica si el comportamiento es muy distinto.
- **Cambio en wizard**: actualizar paso 2.
- **Cambio en endpoints API**: actualizar el endpoint en su paso correspondiente.
- **Cambio en env vars**: actualizar `Configuración necesaria (env vars)` del
  paso 7.

Cualquier ampliación significativa del comportamiento debería ir acompañada de
una bump SemVer (MINOR o MAJOR según rompa contrato o no) y reflejarse aquí en
el commit que la introduce. Si una sección queda completamente obsoleta porque
se eliminó la funcionalidad, márcala como `### [OBSOLETO desde vX.Y.Z]` y
muévela al final del documento como referencia histórica antes de borrarla en
un sprint posterior.
