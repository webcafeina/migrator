# ISSUES — Webcafeína Migrator

Registro local de tareas pendientes mientras no exista repo en GitHub. Cada entrada tiene un **ID estable** (`WCM-NNN`) que se preservará al migrar a GitHub Issues.

## Convenciones

- **Estado**: `OPEN` | `IN_PROGRESS` | `BLOCKED` | `DONE`
- **Tipo**: `feature` | `bug` | `chore` | `docs` | `test` | `infra`
- **Fase**: número de la fase a la que pertenece (0–15)
- **Prioridad**: `P0` (bloqueante) | `P1` (alto) | `P2` (normal) | `P3` (bajo)

Si un TODO en código referencia uno de estos IDs, debe figurar como `# TODO(WCM-NNN): ...` o `// TODO(WCM-NNN): ...`.

---

## Issues abiertos

### WCM-001 — Obtener export JSON real de Bricks Builder mínimo
- **Tipo**: chore / **Fase**: 2 / **Prioridad**: P0
- **Estado**: OPEN
- **Contexto**: El skill `bricks-json-schema` necesita un export real de Bricks (header + hero + texto + CTA + section + container) como referencia canónica del esquema. Sin esto no se puede empezar la Fase 2 (transpilador).
- **Acción**: Instalar Bricks Builder en sandbox WP, crear una página de prueba con los bloques anteriores, exportar JSON, guardar en `.claude/skills/bricks-json-schema/reference-export.json`.
- **Dueño**: equipo Webcafeína.

### WCM-002 — Confirmar datos legales de Webcafeína S.L.
- **Tipo**: docs / **Fase**: 9 / **Prioridad**: P1
- **Estado**: DONE (cerrado en sesión Fase 9, 2026-05-13)
- **Resolución**: CIF B10463990, dirección Santa Cristina s/n – Edificio Embarcadero 10195 Cáceres, URL privacidad https://webcafeina.com/politica-privacidad/ persistidos en `.env` + `apps/api/legal/tratamiento_datos_prospeccion.md`.

### WCM-003 — Calibrar skills de extracción con webs reales
- **Tipo**: chore / **Fase**: 3 / **Prioridad**: P1
- **Estado**: OPEN
- **Contexto**: Los skills `wix-extraction`, `hostinger-ai-extraction` y `webflow-extraction` parten con patrones documentados teóricos. Requieren validación con al menos 3 webs reales por constructor.
- **Acción**: Recolectar 3 URLs públicas representativas por builder, ejecutar el scraper, ajustar selectores, añadir fixtures a `tests/integration/scraper/`.
- **Dueño**: equipo Webcafeína (técnico).

### WCM-004 — Decidir hosting de R2 vs uploads locales por defecto
- **Tipo**: feature / **Fase**: 9 / **Prioridad**: P2
- **Estado**: OPEN
- **Contexto**: Cloudflare R2 está fijado en el stack para assets, pero algunos clientes querrán que los assets vivan solo dentro de su WP destino. Necesitamos flag por proyecto.
- **Acción**: Añadir `projects.asset_storage` (`r2` | `wp_local`) y rama en el asset-optimizer.

### WCM-005 — Confirmar lista ClickUp destino para tareas residuales
- **Tipo**: chore / **Fase**: 10 / **Prioridad**: P2
- **Estado**: OPEN
- **Contexto**: El prompt fija lista "Microtareas" `900102088242` por defecto, pero deberíamos confirmar si para migraciones grandes preferimos lista propia por proyecto.
- **Acción**: Decidir en equipo Webcafeína. Documentar en `docs/decisiones.md`.

### WCM-010 — Local by Flywheel: autodescubrir socket MySQL volátil
- **Tipo**: chore / **Fase**: 4 (descubierto) / **Prioridad**: P3
- **Estado**: OPEN
- **Contexto**: Local genera el socket de MySQL en `~/Library/Application Support/Local/run/<8-char-ID>/mysql/mysqld.sock`. El ID puede cambiar al recrear el site o actualizar Local. `WP_LOCAL_MYSQL_SOCKET` se desactualiza.
- **Acción**: En `WpClientConfig`, si `local_mysql_socket` no está definido pero `local_php_bin` sí, intentar autodescubrir con `find ~/Library/Application\ Support/Local/run -name mysqld.sock 2>/dev/null | head -1` cacheado por sesión.
- **Dueño**: técnico — Fase 4 post-cierre o cuando moleste.

---

### WCM-009 — Local by Flywheel: autodescubrir binario PHP
- **Tipo**: chore / **Fase**: 4 (descubierto) / **Prioridad**: P3
- **Estado**: OPEN
- **Contexto**: Local instala PHP en `~/Library/Application Support/Local/lightning-services/php-8.x.YY+Z/bin/darwin-arm64/bin/php`. Si Local actualiza PHP, la ruta cambia y rompe los tests integración.
- **Acción**: Similar a WCM-010: autodescubrir con `find` la versión más reciente disponible.
- **Dueño**: técnico — Fase 4 post-cierre.

---

### WCM-008 — macOS+Python 3.14: archivos .pth en .venv heredan UF_HIDDEN
- **Tipo**: chore / **Fase**: 2 (descubierto) / **Prioridad**: P2
- **Estado**: DONE (cerrado 2026-05-15, ADR-035)
- **Resolución**: el diagnóstico original era incompleto. La causa real no es la heurística "dot dir = hidden" del propio macOS sino **iCloud Drive sincronizando `~/Desktop/`**: iCloud reaplica `UF_HIDDEN` sobre los ficheros dentro de cualquier directorio dotted cada pocos segundos, anulando el `chflags nohidden` en menos de 5 s. Esto hacía que `scripts/fix-venv-hidden-pth.sh` fuera ineficaz en la práctica (gana la carrera a veces, pierde otras). Solución actual: el venv se llama `venv.nosync/` (sufijo `.nosync` = convención iCloud para excluir) con symlink `venv -> venv.nosync`. El nombre sin punto evita la heurística + el sufijo evita la sincronización iCloud. Verificado: tras 8 s los `.pth` siguen sin flag hidden y los imports funcionan en frío. `fix-venv-hidden-pth.sh` ahora imprime aviso y sale (no se borra para no romper memoria muscular). Doc nueva en `docs/dev-local.md §1`.

---

### WCM-007 — Deduplicar alias de enums en `ts/index.d.ts`
- **Tipo**: chore / **Fase**: 1 (post) / **Prioridad**: P3
- **Estado**: OPEN
- **Contexto**: `pydantic2ts` genera `UserRole1`, `UserRole2`, `OutreachChannel1`, etc. cuando un mismo Enum se referencia desde múltiples schemas. Funcionalmente correcto (los aliases son idénticos), pero feo en autocompletado y reviews.
- **Acción**: Añadir paso post-gen al script `scripts/gen-ts.sh` que detecta duplicados (`type X1 = X` literal) y los reescribe como `export type X1 = X;` o los elimina si son alias triviales. O bien switching a un generador alternativo si `pydantic2ts` no resuelve.
- **Dueño**: equipo Webcafeína (técnico).

---

### WCM-006 — Política de retención de leads sin consentimiento
- **Tipo**: docs / **Fase**: 9 / **Prioridad**: P1
- **Estado**: DONE (cerrado en Fase 10, 2026-05-13)
- **Resolución**: Cron `wcm.maintenance.retention_sweep` implementado en `apps/worker/src/wcm_worker/tasks/maintenance.py`, programado a las 03:30 Europe/Madrid vía Celery beat. Política documentada en `apps/api/legal/politica_retencion.md`. Excepciones (retention_hold para casos AEPD) trackeadas en WCM-013.

---

### WCM-013 — Columna `retention_hold` para excepciones AEPD
- **Tipo**: feature / **Fase**: 10 (post) / **Prioridad**: P2
- **Estado**: OPEN
- **Contexto**: Si la AEPD abre expediente sobre un lead concreto, hay que congelar la retención hasta resolución. Hoy el cron borraría el lead automáticamente al cumplirse el TTL.
- **Acción**: Migración Alembic añadiendo `leads.retention_hold: bool default=false` + `leads.retention_hold_reason: text`. Modificar el cron para excluir registros con `retention_hold=true`. Endpoint admin-only `PATCH /api/v1/leads/{id}/retention-hold`.
- **Dueño**: técnico (post-Fase 10).

---

### WCM-011 — Revisión legal externa de la política de prospección
- **Tipo**: docs / **Fase**: 9 (post) / **Prioridad**: P1
- **Estado**: OPEN
- **Contexto**: `apps/api/legal/tratamiento_datos_prospeccion.md` y plantillas de outreach deben revisarse por asesor legal externo antes de paso a producción. La base 6.1.f + 21.2 LSSI-CE es la lectura interna; cualquier diferencia respecto a la AEPD obligaría a replantear el modelo de contacto.
- **Acción**: Contratar revisión legal con foco en LSSI-CE B2B + interés legítimo. Documentar el resultado en `decisiones.md`.
- **Dueño**: equipo Webcafeína.

---

### WCM-012 — Habilitar Places API (New) cuando sea posible
- **Tipo**: chore / **Fase**: 9 (post) / **Prioridad**: P3
- **Estado**: OPEN
- **Contexto**: La API key del proyecto solo tiene habilitada Places API legacy (ADR-024). La New tiene mejor field-mask y precio. Migrar cuando billing/google permita.
- **Acción**: Habilitar Places API (New) en Google Cloud Console y reescribir `packages/scraper-core/src/wcm_scraper_core/directories/google_places.py` para usar `places.googleapis.com/v1/places:searchText`. Tests con MockTransport siguen valiendo.
- **Dueño**: técnico.

---

### WCM-021 — E2E con mock server real para Server Components
- **Tipo**: test / **Fase**: 13 (post) / **Prioridad**: P2
- **Estado**: OPEN (3 tests skipped tras primer CI run)
- **Contexto**: `page.route()` de Playwright intercepta requests del **browser**, no de los Server Components que hacen fetch en Node. Las páginas `/leads`, `/leads/[id]`, `/projects`, `/projects/[id]` son Server Components y por eso sus fetch van directos al API real → ECONNREFUSED en CI sin API levantada. 3 tests skipped: `Leads`/`acceso a detalle del lead`, `Proyectos`/`listado y navegación al detalle`.
- **Acción**: Una de estas opciones:
  - (a) Levantar **MSW node** en el `webServer.command` de Playwright para interceptar el fetch a nivel Node.
  - (b) Levantar un mini servidor HTTP en otro puerto que sirva fixtures, y apuntar `API_URL=http://127.0.0.1:<puerto-mock>` en el webServer env.
  - (c) Levantar la API real (FastAPI con Postgres+Redis) como service en el job e2e — complejo.
- Recomendado: opción (a) MSW node. Mantenibilidad alta y compartido con vitest si hace falta.
- **Dueño**: técnico — abordable en Fase 16+ (post-v0.1.0).

---

### WCM-022 — Comando `wcm users create` para seed admin sin script ad-hoc
- **Tipo**: feature / **Fase**: post-v0.1.0 / **Prioridad**: P2
- **Estado**: OPEN
- **Contexto**: el dev local actual requiere ejecutar un script Python ad-hoc para crear el primer admin. Tener `wcm users create --email --name --role --password` simplifica el setup.
- **Acción**: nuevo módulo `cli/src/wcm_cli/commands/users.py` con subcomandos `create`, `list`, `set-role`, `deactivate`. Hash con argon2 reusando `wcm_api.security.hash_password`.

---

### WCM-023 — `scripts/dev-up.sh` para arrancar la stack con un solo comando
- **Tipo**: chore / **Fase**: post-v0.1.0 / **Prioridad**: P2
- **Estado**: OPEN
- **Contexto**: actualmente el dev local requiere 4 terminales (API + worker + beat + dashboard). Mala DX.
- **Acción**: script bash con `concurrently` (npm) o `tmux` que arranque los 4 procesos con sus envs y logs separados por color. Trap SIGINT para parar todo en cascada con Ctrl+C.

---

### WCM-024 — `infra/whm-setup/02-database.sh` con flag `--macos-local`
- **Tipo**: chore / **Fase**: post-v0.1.0 / **Prioridad**: P3
- **Estado**: OPEN
- **Contexto**: el script asume Linux con `sudo -u postgres`. En macOS brew, el superusuario es el usuario actual; los comandos son `psql postgres -c "CREATE ROLE..."` directos. Documentado en `docs/dev-local.md`.
- **Acción**: añadir flag `--macos-local` al script que detecta plataforma y usa el equivalente sin sudo.

---

### WCM-025 — ADR-034 documentando GlitchTip como backend error tracking
- **Tipo**: docs / **Fase**: post-v0.1.0 / **Prioridad**: P3
- **Estado**: OPEN
- **Contexto**: en testeo local 2026-05-14 se eligió GlitchTip hosted como alternativa gratuita a Sentry (free 1k eventos/mes perpetuo, API 100% compatible con sentry-sdk — drop-in). ADR-028 menciona Sentry sin diferenciar backend.
- **Acción**: redactar ADR-034 "GlitchTip hosted en vez de Sentry SaaS". Marcar ADR-028 con nota cruzada.

---

### WCM-026 (CRÍTICO) — `ProspectorAgent` no encadena fingerprint + enrich
- **Tipo**: bug / **Fase**: 9 (descubierto en dev-local 2026-05-14, fix aplicado) / **Prioridad**: **P0**
- **Estado**: RESUELTO (2026-05-14)
- **Contexto**: la task `wcm.prospector.run_campaign` solo creaba leads `DISCOVERED`. No encolaba fingerprint ni enrich después. Los leads se quedaban colgados sin contacto/score.
- **Resolución**: `ProspectorAgent.run()` ahora devuelve `outputs["created_lead_ids"]`. La task `tasks/prospector.run_campaign` itera esa lista y por cada lead encola un `chain(wcm.fingerprinter.run, wcm.enricher.run)` (signatures immutable). Verificado e2e: campaña "cafetería"/"Mérida"/target=3 → 2 leads creados → fingerprint+enrich automáticos.

---

### WCM-027 (CRÍTICO) — Falta task Celery + endpoint + CLI para enrich
- **Tipo**: feature / **Fase**: 9 (descubierto en dev-local 2026-05-14, fix aplicado) / **Prioridad**: **P0**
- **Estado**: RESUELTO (2026-05-14)
- **Contexto**: existía `EnricherAgent` pero no se exponía: sin task Celery, sin endpoint, sin CLI.
- **Resolución**:
  - `apps/worker/src/wcm_worker/tasks/enricher.py` con `@celery_app.task(name="wcm.enricher.run")` (acepta `skip_embedding` opcional).
  - `enqueue_lead_enrich(lead_id, *, skip_embedding=False)` en `apps/api/src/wcm_api/tasks/enqueue.py`.
  - `POST /api/v1/leads/{id}/enrich?skip_embedding=true` con rol operator/admin.
  - `wcm leads enrich <id> [--skip-embedding]` en el CLI.
  - 7 tests del endpoint + 5 del task chain.

---

### WCM-028 — Warning estático obsoleto en `wcm campaigns launch`
- **Tipo**: bug / **Fase**: 7 (CLI) / **Prioridad**: P3
- **Estado**: RESUELTO (2026-05-14)
- **Contexto**: el comando imprimía `⚠ ProspectorAgent es stub en Fase 6. Implementación real en Fase 9.` — texto hardcodeado obsoleto.
- **Resolución**: reemplazado por `output.info(...)` con mensaje real ("El worker descubrirá leads vía Google Places y los pasará por fingerprint + enrich automáticamente").

---

### WCM-029 — `.env.example` debe usar `postgresql+psycopg://` para DATABASE_SYNC_URL
- **Tipo**: bug / **Fase**: post-v0.1.0 / **Prioridad**: P2
- **Estado**: OPEN
- **Contexto**: `.env.example` tiene `DATABASE_SYNC_URL=postgresql://...` sin prefix de driver. SQLAlchemy intenta `psycopg2` (no instalado — usamos `psycopg` v3). Alembic falla con `ModuleNotFoundError: psycopg2`. Prefix `+psycopg` necesario.
- **Acción**: actualizar `.env.example` línea de `DATABASE_SYNC_URL` con el prefix correcto.

---

### WCM-030 — `greenlet` no estaba en deps explícitas del API
- **Tipo**: bug / **Fase**: 5 (API) / **Prioridad**: P2
- **Estado**: OPEN
- **Contexto**: SQLAlchemy async (asyncpg) requiere `greenlet`. Sin él, `/health/deep` falla con `the greenlet library is required to use this function`. Funcionó en CI porque algún transitivo lo arrastra, en venv limpio no.
- **Acción**: añadir `greenlet>=3.0` a `apps/api/pyproject.toml` deps.

---

### WCM-031 (CRÍTICO) — `ProspectorAgent` no llamaba a `place_details`; ningún lead se creaba
- **Tipo**: bug / **Fase**: 9 (descubierto en dev-local 2026-05-14, fix aplicado) / **Prioridad**: **P0**
- **Estado**: PARCIALMENTE RESUELTO (fix local aplicado en commit pendiente)
- **Contexto**: Google Places Text Search legacy NO devuelve `website` ni `phone` en sus resultados — solo `place_id`, `name`, `address`, `types`. El `ProspectorAgent` filtraba con `if not place.website` que SIEMPRE era None → todos los places descartados como `no_website` → 0 leads creados nunca. **El producto MVP no producía leads en producción**.
- **Resolución parcial**: fix aplicado en sesión 2026-05-14. Ahora se hace `place_details(place_id)` por cada place tras el filtro de tipo. Verificado: campaña "restaurante" / "Cáceres" / target=5 → 5 leads creados con URLs reales.
- **Pendiente**: commit + push del fix; test unit en `test_prospector.py` que cubra el flujo Text Search devolviendo `website=None` y place_details devolviendo `website` real; documentar coste extra (~N+1 calls Places por campaña).

---

### WCM-032 (CRÍTICO) — Dashboard no podía autenticar contra el API
- **Tipo**: bug / **Fase**: 5 (API auth) / **Prioridad**: **P0**
- **Estado**: RESUELTO (2026-05-14)
- **Contexto**: `get_current_user_payload` en `apps/api/src/wcm_api/security.py` solo aceptaba `Authorization: Bearer` o `x-wcm-token`. Un comentario decía *"Cookie `<session_cookie_name>` (vía middleware que la inyecta como header)"* pero **ese middleware nunca se implementó**. Resultado: cualquier acción desde el dashboard que llamara al API daba "Credenciales no proporcionadas" — incluido lanzar campaña, listar leads, etc.
- **Resolución**: la dependency ahora recibe `request: Request` y, como tercer fallback, lee `request.cookies.get(settings.session_cookie_name)`. Respeta el nombre configurable de la cookie sin necesidad de middleware. 19 tests de auth siguen verdes.

---

### WCM-033 — Worker Celery con SIGSEGV al cargar embeddings en macOS
- **Tipo**: bug / **Fase**: 9 (descubierto en dev-local 2026-05-14, fix aplicado) / **Prioridad**: P1
- **Estado**: RESUELTO en dev (2026-05-14)
- **Contexto**: `EnricherAgent` carga el modelo `intfloat/multilingual-e5-large` (sentence-transformers/PyTorch). En macOS, Celery con `--pool=prefork --concurrency=2` hace `fork()` después de inicializar PyTorch → `WorkerLostError: signal 11 (SIGSEGV)`. Confirmado en macOS 25.5 Darwin con Python 3.14.4.
- **Resolución**: `scripts/dev-up.sh` arranca el worker con `--pool=threads --concurrency=2`. Sin fork, sin segfault. En Linux/prod (systemd) se puede volver a prefork sin problema porque ahí PyTorch sí tolera fork.
- **Pendiente**: añadir nota en `docs/dev-local.md` sobre esta diferencia macOS/Linux; considerar flag `WCM_WORKER_POOL` en `infra/systemd/webcafeina-worker.service` para parametrizar (no ahora, no urgente).

---

### WCM-034 — Extender rediseño visual a `/projects/[id]` + sub-páginas
- **Tipo**: feature / **Fase**: post-MVP rediseño / **Prioridad**: P1
- **Estado**: DONE (cerrado en v0.8.0, 2026-05-18)
- **Resolución**: rediseñado en 5 bloques (`64908c1` → `98b8591`):
  endpoint `/projects/{id}/summary` con agregados + 4 componentes
  shared (`ProjectHeader`, `ProjectTabs`, `PhaseProgressBar`,
  `ProjectPhasesTimeline`) + refactor de las 3 sub-páginas
  (overview, checklist, diff) + spec Playwright. Verificación visual
  con fixture de proyecto en desktop + mobile. Bug menor P0 cerrado:
  el placeholder de diff decía "se implementa en Fase 10" — mentira
  desde hace meses; ahora reconoce que `packages/visual-diff/` ya
  existe y solo falta conectarlo a la UI.

---

### WCM-035 — Extender rediseño a `/errors` y `/residual-tasks` — **CERRADO v0.9.0**
- **Tipo**: feature / **Fase**: post-MVP rediseño / **Prioridad**: P2
- **Estado**: DONE 2026-05-18 (commits `a146528`, `e832b53`, `8106474`, `707bc95`).
- **Resolución**: rediseñadas ambas pantallas en sprint único v0.9.0
  bajo patrón ADR-036. Endpoints `/stats` específicos (8 buckets errors,
  9 residuales), KpiStrip + FilterChips reusados, ErrorsTable con
  SeverityBadge 5 colores, ResidualTasksTable con CategoryBadge para
  blocking_go_live y StatusPill castellana. Empty states 2 ramas
  (systemEmpty lima con mención de Sentry/checklist-generator vs filtro
  neutro). Quedan filtros por componente y por rango fecha como mejora
  futura no bloqueante.

---

### WCM-049 — Vaporware "Convertir a proyecto" (Fase 7) — **CERRADO v0.13.0**
- **Tipo**: bug / **Fase**: post-rediseño / **Prioridad**: P0
- **Estado**: DONE 2026-05-18 (commit `117d974`).
- **Resolución**: `ConvertToProjectDialog` con form pre-rellenado
  desde lead → POST /projects → redirect a /projects/{id}. Endpoint
  ya existía; el botón estaba disabled vaporware desde v0.3.0.

---

### WCM-050 — Vaporware "Marcar opt-out" — **CERRADO v0.13.0**
- **Tipo**: bug / **Fase**: post-rediseño / **Prioridad**: P0
- **Estado**: DONE 2026-05-18 (commit `117d974`).
- **Resolución**: `MarkOptOutDialog` con nota libre → POST
  /leads/{id}/consent action=objection_received. Endpoint ya existía
  (Fase 9 RGPD).

---

### WCM-051 — Vaporware Runbook menciona `wcm users` inexistente — **CERRADO v0.13.0**
- **Tipo**: bug / **Fase**: post-rediseño / **Prioridad**: P0
- **Estado**: DONE 2026-05-18 (commits `8e1efb9`, `07fd7c4`).
- **Resolución**: CLI `wcm users` real (6 comandos + 10 tests) + UI
  /admin/users admin-only con CRUD completo + endpoint PATCH
  /users/{id} nuevo + Runbook actualizado con link real.

---

### WCM-052 — Gaps operativos UI: audit-log + contactos cross-lead — **CERRADO v0.13.0**
- **Tipo**: feature / **Fase**: post-rediseño / **Prioridad**: P1
- **Estado**: DONE 2026-05-18 (commits `ff8ee0b`, `2a5fbe5`).
- **Resolución**: página /audit-log dedicada con filtros (action/
  entity_type/actor/since) reemplazando feed mini de homepage; vista
  global /contactos cross-lead con KpiStrip + FilterChips por status
  + tabla con link a ficha lead. Sidebar amplía con ambas entradas.

---

### WCM-048 — Cerrar flujo §8 paso 6 (Aprobar→Enviar) en UI + CLI — **CERRADO v0.12.1**
- **Tipo**: bug + feature / **Fase**: post-rediseño ampliación funcional / **Prioridad**: P0
- **Estado**: DONE 2026-05-18 (commits `94c83e3`, `c71fe4f`, +hotfix polling).
- **Contexto**: tras E2E manual el usuario reportó 3 problemas: (1)
  Aprobar no transicionaba a READY en UI aunque el backend sí; (2)
  status badges mostraban enum en bruto sin castellanizar; (3) tras
  aprobar no había forma de enviar realmente — flujo se interrumpía.
- **Resolución**:
  - Bug fix: `replaceSequence` actualiza state local con response del
    POST (router.refresh no re-monta Client child).
  - i18n: helpers `sequenceStatusLabel`/`sendStatusLabel` en labels.ts.
  - Acciones expandidas: Aprobar/Pausar/Cancelar/Enviar condicionales
    por status. Aprobar visible-disabled (no oculto) si !legalPassed
    con tooltip que dirige a editar el paso.
  - Vista tracking de envíos por step + polling automático (4s)
    mientras hay sends QUEUED o sequence IN_PROGRESS.
  - CLI completo `wcm outreach list/show/approve/pause/cancel/send`.

---

### WCM-043 — Editar correos de contacto sugeridos — **CERRADO v0.12.0**
- **Tipo**: feature / **Fase**: post-rediseño ampliación funcional / **Prioridad**: P1
- **Estado**: DONE 2026-05-18 (commits `1549ef4`, `7c1563c`).
- **Resolución**: `PATCH /api/v1/outreach/sequences/{id}/steps` con
  semántica de reemplazo + re-validación legal. Editor inline
  `SequenceStepEditor` con subject/body/delay. Si la edición rompe
  el footer legal, la sequence queda no-aprobable hasta corregir.

---

### WCM-044 — Eliminar leads (soft + hard) — **CERRADO v0.12.0**
- **Tipo**: feature / **Fase**: post-rediseño ampliación funcional / **Prioridad**: P1
- **Estado**: DONE 2026-05-18 (commit `d24bb71`).
- **Resolución**: `POST /leads/{id}/discard` (soft, idempotente) y
  `DELETE /leads/{id}` (hard con CASCADE) + UI con botones outline
  ámbar y rojo + `LeadDeleteDialog` typing-to-confirm + listado oculta
  DISCARDED por defecto. CLI `wcm leads discard|delete --confirm`.

---

### WCM-045 — CRUD plantillas Jinja2 desde dashboard — **CERRADO v0.12.0**
- **Tipo**: feature / **Fase**: post-rediseño ampliación funcional / **Prioridad**: P1
- **Estado**: DONE 2026-05-18 (commits `1549ef4`, `5dc9f5d`).
- **Resolución**: tabla `outreach_templates` nueva (migración Alembic
  0003) + router CRUD admin-only para escritura + pantalla
  `/settings/templates` con master-detail. Composer refactorizado
  para leer plantillas de BD con fallback a `.j2`. `name` no editable
  para no romper sequences históricas.

---

### WCM-046 — Refactor castellano "outreach" → "contacto comercial" — **CERRADO v0.12.0**
- **Tipo**: refactor UI / **Fase**: post-rediseño / **Prioridad**: P2
- **Estado**: DONE 2026-05-18 (commit `ead57b5`).
- **Resolución**: copy castellano visible al usuario actualizado en 6
  sitios + componente `OutreachSequencePanel` renombrado a
  `ContactSequencePanel` (git mv preserva historial). URLs API,
  columnas BD y módulos Python intactos. Anchor `#outreach` se
  mantiene (id técnico).

---

### WCM-047 — Firma legal visible read-only en /settings — **CERRADO v0.12.0**
- **Tipo**: feature / **Fase**: post-rediseño / **Prioridad**: P2
- **Estado**: DONE 2026-05-18 (commit `ead57b5`).
- **Resolución**: nuevo endpoint `GET /system/firma` admin/operator +
  `FirmaCard` Client en /settings que muestra los datos legales
  aplicados al composer. Read-only (editar via SSH + systemctl).
  Warning rojo si COMPANY_CIF o COMPANY_ADDRESS faltan en env.

---

### WCM-041 — Sin progreso visible tras alta manual de lead — **CERRADO v0.11.1**
- **Tipo**: bug / **Fase**: post-rediseño / **Prioridad**: P1
- **Estado**: DONE 2026-05-18 (commit `681121d`).
- **Contexto**: tras `POST /leads` el redirect a `/leads?selected=N`
  mostraba el lead en `discovered` sin polling. Operador no veía el
  avance del pipeline (fingerprint → enrich) hasta hacer F5.
  Detectado por el usuario en E2E manual tras v0.11.0.
- **Resolución**: `LeadStatusPoller` Client que llama
  `router.refresh()` cada 4s mientras `status ∈ {discovered,
  fingerprinted}`. Indicador visual contextual ("Fingerprint en
  curso…" / "Enriquecimiento en curso…"). Para cuando llega a
  terminal. 6 tests vitest con fake timers.

---

### WCM-042 — "Revisar" del banner outreach lleva a vaporware — **CERRADO v0.11.1**
- **Tipo**: bug / **Fase**: post-rediseño / **Prioridad**: P0
- **Estado**: DONE 2026-05-18 (commit `dd272f6`).
- **Contexto**: `DraftBanner` enlazaba a `/leads/{id}#outreach` con
  comentario explícito "futura sección (cuando exista)". La sección
  nunca se implementó. Bloqueaba el paso 6 del flujo §8 (operador
  revisa/aprueba outreach) — clase de vaporware como "Fase 10"
  v0.8.0 y "Fase 14" v0.10.0.
- **Resolución**: `OutreachSequencePanel` Client en `LeadDetailPane`
  con sección `id="outreach"`. Fetcha
  `/api/v1/outreach/sequences?lead_id=N`, renderiza cada sequence
  con sus pasos (subject + body line-breaks preservados + delay),
  botón "Aprobar" → `POST /transition action=approve` habilitado
  solo si DRAFT_PENDING_REVIEW + legal_validation_passed.
  Adicionalmente fix de schema `OutreachStep` con `extra="allow"` +
  `AliasChoices` para tolerar sequences legacy en BD que rompían
  el endpoint con 500. 10 tests vitest.

---

### WCM-040 — Alta manual de leads (single + bulk) — **CERRADO v0.11.0**
- **Tipo**: feature / **Fase**: post-rediseño ampliación funcional / **Prioridad**: P1
- **Estado**: DONE 2026-05-18 (commits `aa43968`, `b5ecb47`, `511fd4c`, `72c751f`, `303bb80`).
- **Contexto**: el usuario detectó al hacer E2E manuales en /leads que
  no había forma de añadir URLs concretas sin pasar por una campaña
  Google Places. Bloqueaba poder probar el flujo de prospección + el
  de migración sobre webs específicas.
- **Resolución**: 2 endpoints (`POST /leads` + `POST /leads/bulk`),
  página `/leads/new` con tabs ARIA single/bulk + preview live,
  `wcm leads create` CLI con XOR `--url`/`--bulk-file`, encadenado
  automático fingerprint+enrich tras alta. `normalize_lead_url`
  extraído a `wcm_scraper_core.urls` como single source of truth
  para canonicalización (compartido prospector + endpoint).
  AuditLog mantiene `legal_ground="6.1.f"`; procedencia en
  `payload.source`. 11 tests pytest + 15 vitest + 8 cli + 8 playwright.
  `CliApiError` ahora propaga `details` del envelope del API.

---

### WCM-039 — Rediseño `/settings` — cierre del ciclo completo — **CERRADO v0.10.0**
- **Tipo**: feature / **Fase**: post-MVP rediseño / **Prioridad**: P2
- **Estado**: DONE 2026-05-18 (commits `b44a99f`, `8936af0`, `67e07a1`, `a7d4baa`, `69a1bce`).
- **Resolución**: rediseñada la última pantalla del dashboard bajo el
  patrón ADR-036 con la variación para pantallas no-list. Endpoint
  `/api/v1/system/info` con 6 campos de runtime + 3 componentes
  presentacionales (`UserCard`, `SystemInfoPanel` con HealthRows,
  `OperationRunbook`) + refactor 2-col + spec Playwright 7 tests.
  Castellanización del título ("Settings" → "Ajustes"). Bug P0
  eliminado: "UI de gestión: Fase 14" (misma clase que la "Fase 10"
  del diff cerrada en WCM-034). Con esto **11/11 pantallas
  operativas del dashboard quedan bajo el nuevo lenguaje visual**;
  `/login` queda fuera de scope por vivir en otro app group.

---

### WCM-036 — 3 vitest skipped por React 19 + `startTransition(async)`
- **Tipo**: test / **Fase**: post-MVP rediseño / **Prioridad**: P3
- **Estado**: OPEN
- **Contexto**: en `tests/campaigns-launch-form.test.tsx` (v0.6.0) hay
  3 tests `.skip(...)` porque los side-effects posteriores a un `await`
  dentro de `startTransition(async () => ...)` no se propagan de forma
  fiable en happy-dom + React 19 + Vitest. El handler se ejecuta y
  `api.post` se llama (verificable), pero `toast.error` y
  `router.refresh` posteriores quedan colgados.
- **Acción**: investigar al actualizar React 19 o Vitest. Opciones:
  (a) migrar de happy-dom a jsdom; (b) wrap explícito con `act()`;
  (c) refactor del componente para no usar `startTransition` con
  async; (d) esperar a que WCM-021 (MSW node) cubra el flujo en
  Playwright y aceptar el gap en vitest.
- **Dueño**: técnico, no urgente.

---

### WCM-037 — Promoción "componentes shared cuando lo usan 2+ páginas"
- **Tipo**: docs / **Fase**: post-MVP rediseño / **Prioridad**: P3
- **Estado**: OPEN (criterio aplicado de facto desde v0.5.0)
- **Contexto**: 2 movimientos ya hechos: `FilterChips` (v0.5.0,
  movido de `/leads/_components` a `components/`) y `KpiStrip`
  (v0.7.0, movido de `/_overview/` a `components/`). El criterio es
  consistente pero solo vive en commits — convendría doc explícito
  para que el equipo replique sin discusión.
- **Acción**: añadido informalmente en ADR-036 §"Componentes
  compartidos". Si crece, un sub-ADR dedicado.
- **Dueño**: docs (resuelto en ADR-036, mantener vigilancia).

---

### WCM-038 — Limpiar `.next/types/* [N]*.ts` duplicados por iCloud
- **Tipo**: chore / **Fase**: post-MVP / **Prioridad**: P3
- **Estado**: OPEN (workaround manual)
- **Contexto**: iCloud Drive (mismo problema que causó ADR-035 con
  el venv) duplica también archivos generados por Next dentro de
  `apps/dashboard/.next/types/` con sufijo ` 2.ts`, ` 3.ts`, etc.
  Esto rompe `tsc --noEmit` con `TS2300: Duplicate identifier
  'LayoutProps'`. Detectado en preflight de v0.7.0.
- **Acción**: opciones:
  (a) Añadir `find apps/dashboard/.next -name "* [0-9]*" -delete`
      como pre-step de `pnpm exec tsc --noEmit`.
  (b) Añadir `.next/` al `xattr -w com.apple.fileprovider.ignore#P 1`
      como hicimos con `venv.nosync/`.
  (c) Mover el repo fuera de `~/Desktop/` (solución de raíz también
      para el venv).
  Por ahora workaround manual: `find ... -delete` cuando aparezca.
- **Dueño**: técnico.

---

### WCM-039 — Distributed lock por project_id en wcm.orchestrator.run_project
- **Tipo**: bug / **Fase**: post-v0.27.0 / **Prioridad**: P1
- **Estado**: OPEN
- **Contexto**: Detectado en E2E v0.27.0 B9 (proyectos 29 y 30).
  `task_acks_late=True` (celery_app.py) + `visibility_timeout` Redis
  por defecto (3600s) provocan que, si el worker se reinicia mientras
  un orchestrator está corriendo, Redis hace **redelivery del mismo
  task_id 1h después** al worker que vuelve. Resultado: 2 instancias
  del mismo task corriendo en paralelo. Síntomas observados:
    - Proyecto 29: race condition en `_mark_phase` (UniqueViolation,
      resuelto con UPSERT atómico).
    - Proyecto 30: 675 assets duplicados creados por la fase
      scrape_origin re-ejecutada por la copia redelivery (676 → 1351).
  El UPSERT atómico **mitiga** el corruption de project_phases pero
  no impide la doble ejecución de fases I/O-bound (scrape, optimize,
  redesign_ai con doble coste OpenAI).
- **Acción**: implementar lock distribuido en `run_project` con Redis
  SETNX + TTL renovable. Pseudocódigo:
  ```python
  lock_key = f"wcm:orchestrator:lock:project:{project_id}"
  acquired = redis.set(lock_key, task_id, nx=True, ex=86400)
  if not acquired:
      log.warning("orchestrator_already_running_skip", project_id=project_id)
      return {"skipped": True, "reason": "duplicate_task"}
  try: orch.run_project(project_id)
  finally: redis.delete(lock_key) if redis.get(lock_key) == task_id else None
  ```
  Heartbeat opcional para refrescar TTL si fases largas (>24h
  improbable, pero conviene). Considerar también bajar
  `task_acks_late=False` para `wcm.orchestrator.run_project`
  específicamente (idempotencia a nivel app, no broker).
- **Dueño**: técnico (siguiente sprint, no bloqueante para release v0.27.0
  si E2E B9 se cierra con cleanup manual de assets duplicados).

---

### WCM-053 (CRÍTICO) — BriefGenerator emite secciones de bajo nivel; SectionPicker no matchea catálogo brickstemplate
- **Tipo**: bug / **Fase**: v0.28.0 B8 (descubierto en E2E mariya.design 2026-06-02) / **Prioridad**: **P0**
- **Estado**: OPEN — bloquea cierre v0.28.0 y E2E B8/B9.
- **Contexto**: ejecutado E2E manual sobre mariya.design (proyecto 32) con design_method=hybrid. El pipeline llegó hasta `redesign_templates` pero solo resolvió **10/1550 secciones (0,6%)** y emitió **1540 residuals** `template_not_found_for_section`. Causa raíz: `BriefGenerator` crea una `Brief.section` por cada bloque HTML extraído (`content_extractor.blocks`). Distribución observada: text(1114), heading(275), image(85), grid(58), hero(10), form(6), accordion(1), tabs(1). El catálogo brickstemplate.com (482 templates) está categorizado en taxonomía semántica: hero(44), features(36), cta(34), header(46), footer(33), pricing(20), team(14), testimonials(15), faqs(12), etc. **Único cruce válido: `hero`** → 10 matches; el resto cae al fallback "skip + residual". Se gastaron ~$0.29 en gpt-image-2 para imágenes hero (sin Bricks render real porque `bricks_adapt` no llegó a correr con shape válido).
- **Acción**: introducir nuevo agente `BriefSectionAggregator` entre `brief_generator` y `redesign_templates` que reagrupe los bloques de bajo nivel en secciones semánticas (hero, features, cta, footer, pricing, contact_form, faqs, products, header, gallery, testimonials, team, banner, brands) usando gpt-5.5 con tool_use forzado. Cache por `(page_id, blocks_hash)` para idempotencia y reentry. Coste objetivo <$0.50/proyecto. Sprint v0.29.0.
- **Mitigación temporal**: ninguna — sin el agregador el pipeline Hybrid es inútil para origen real (Wix/Webflow producen miles de bloques planos).
- **Dueño**: técnico — sprint v0.29.0.

---

## Plantilla para nuevos issues

```
### WCM-NNN — Título corto
- **Tipo**: feature|bug|chore|docs|test|infra / **Fase**: N / **Prioridad**: P0|P1|P2|P3
- **Estado**: OPEN
- **Contexto**: ...
- **Acción**: ...
- **Dueño**: humano | técnico | a asignar
```
