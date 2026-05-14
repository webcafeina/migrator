# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Versionado [SemVer](https://semver.org/lang/es/).

---

## [Unreleased]

Cambios todavía sin tag.

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
