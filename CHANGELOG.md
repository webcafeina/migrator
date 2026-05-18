# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Versionado [SemVer](https://semver.org/lang/es/).

---

## [Unreleased]

Cambios todavía sin tag.

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
