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
- **Fase 12 — Infra/Deploy**: ✅ Completada (commit `7c6b8a0`)
- **Fase 13 — Tests e2e**: ✅ Completada (commit `891553a`)
- **Fase 14 — Documentación**: ✅ Completada (commit `d1b2b86`)
- **Fase 15 — Hardening**: ✅ Completada esta sesión (commit `5691199`)
- **MVP v0.1.0 CERRADO** (2026-05-14) — repo público en https://github.com/webcafeina/migrator, release v0.1.0 publicada. Branch protection activado en `main`. CI verde. Roadmap post-v0.1.0 en ISSUES.md WCM-011..WCM-021.
- **Post-MVP: rediseño visual del dashboard** — ✅ CERRADO con v0.10.0 (2026-05-18). 11/11 pantallas operativas bajo el nuevo lenguaje.
- **Post-rediseño: ampliación funcional** EN CURSO desde v0.11.0 (2026-05-18). Primer sprint sobre el dashboard ya rediseñado, sin tocar lenguaje visual — añadir features que faltaban para hacer E2E manuales del flujo de prospección y migración.

## Última versión publicada

**v0.11.1** (2026-05-18) — hotfix de 2 bugs detectados en E2E manual:
polling vivo del status del lead mientras el pipeline corre
(`LeadStatusPoller`), y sección outreach real en la ficha del lead
(`OutreachSequencePanel`) que sustituye el placeholder vaporware al
que enlazaba "Revisar". Schema `OutreachStep` tolerante a sequences
legacy. WCM-041 + WCM-042 cerrados. CI verde.

**v0.11.0** (2026-05-18) — alta manual de leads (single + bulk) en
dashboard y CLI. Endpoints `POST /api/v1/leads` y `/leads/bulk` con
encadenado automático fingerprint+enrich. Página `/leads/new` con tabs
ARIA + preview live de URLs válidas. `wcm leads create` con XOR
`--url`/`--bulk-file`. AuditLog mantiene `legal_ground=6.1.f` (interés
legítimo B2B); procedencia en `payload.source`. CI verde.

## Estado del rediseño visual del dashboard

| # | Pantalla | Estado | Release |
|---|---|---|---|
| 1 | `/login` | fuera de scope | — (app group `(auth)`) |
| 2 | `/` Panel | ✅ rediseñado | v0.5.0 |
| 3 | `/campaigns` | ✅ rediseñado + fix P0 | v0.6.0 + v0.6.1 |
| 4 | `/leads` master-detail | ✅ rediseñado | v0.4.0 |
| 5 | `/leads/[id]` full-page | ✅ refactor | v0.6.0 |
| 6 | `/projects` | ✅ rediseñado | v0.7.0 |
| 7-9 | `/projects/[id]` + `checklist` + `diff` | ✅ rediseñado | v0.8.0 |
| 10 | `/errors` | ✅ rediseñado | v0.9.0 |
| 11 | `/residual-tasks` | ✅ rediseñado | v0.9.0 |
| 12 | `/settings` | ✅ rediseñado | **v0.10.0** |

**Patrón de rediseño consolidado** tras 6 pantallas (ADR-036, con
variación documentada para pantallas no-list en v0.10.0):
1. Endpoint backend dedicado (`/X/stats` para listados; `/system/info`
   o equivalente para pantallas informativas).
2. Componentes presentacionales en `_components/`.
3. Refactor `page.tsx` denso (`KpiStrip` + chips + tabla/empty para
   listados; kv-grid + sub-bloques para informativas).
4. Pulido: empty states diferenciados (listados) o verificación
   responsive (informativas).
5. Tests: vitest del componente + spec Playwright (mitad ejecutable,
   mitad skipped por WCM-021).

Componentes promovidos a `apps/dashboard/src/components/` (shared):
`FilterChips` (v0.5.0), `KpiStrip` (v0.7.0).

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
| 13 | Tests e2e | ✅ Completada | Playwright + 4 specs (login/leads/projects/visual) con API mockeada via page.route(); 5 e2e Python pipeline (orchestrator + stubs reales + stateful_session); coverage 74.8% con pytest-cov; CI matrix Py 3.13/3.14 × Node 20/22 (ADR-032). Total 384+15+8 Playwright. |
| 14 | Documentación | ✅ Completada | arquitectura.md (5 diagramas Mermaid + tabla 21 agentes) + prospeccion.md (10 secciones operador) + migracion.md (13 secciones operador) + playbook-operativo.md (10 runbooks INC-NN) + glossary.md (40+ términos) + README quickstart operador. |
| 15 | Hardening | ✅ Completada | pip-audit + pnpm audit (0 vulns tras postcss override); slowapi rate-limit en login/compose/send/opt-out; security audit doc v0.1.0; performance SLOs; CHANGELOG; release-v0.1.0.md con instrucciones push; ADR-033. Total 387 Py + 15 TS + 8 Playwright = 410 tests. |

---

## Sesiones post-MVP (rediseño visual del dashboard)

Trabajo posterior al cierre del MVP v0.1.0. Cada release agrupa un
rediseño completo de una pantalla (5 bloques granulares — ver ADR-036).

### v0.11.0 — Alta manual de leads (single + bulk) — 2026-05-18

Primer sprint de ampliación funcional sobre el dashboard ya rediseñado
(NO toca lenguaje visual). El usuario detectó al hacer E2E manuales
que no había forma de añadir URLs concretas al sistema sin pasar por
una campaña de Google Places — el flujo de prospección dependía
totalmente del crawler. Esto cierra esa brecha.

Aplica el patrón ADR-036 (5 bloques granulares) adaptado a "feature
nueva sobre página existente" en vez de "rediseño completo":

- `POST /api/v1/leads` (single, 201) + `POST /api/v1/leads/bulk` (200
  con `LeadBulkCreateResult` agregado, hasta 200 URLs por batch,
  rate-limit 10/min, NO aborta el batch ante fallos aislados).
  `_insert_lead` helper compartido con `pg_insert.on_conflict_do_nothing`.
  Fire-and-forget de `enqueue_lead_fingerprint` + `enqueue_lead_enrich`
  tras commit (si Celery cae, lead persiste y warning en log).
  AuditLog DISCOVER con `legal_ground="6.1.f"` igual que el
  ProspectorAgent — la base RGPD no cambia por procedencia.
  `payload.source` distingue `manual_single` / `manual_bulk`.
  11 tests pytest (`aa43968`).
- `normalize_lead_url` extraído de prospector a
  `wcm_scraper_core.urls` — single source of truth para
  canonicalización; strippea querystring (UTMs/fbclid) + fragment +
  www + trailing slash. ProspectorAgent ahora importa de ahí.
- `LeadCreateForm` con tabs ARIA single/bulk (useState, no
  searchParams). `LeadCreateSingleTab` réplica del LaunchCampaignForm.
  `LeadCreateBulkTab` con textarea + `BulkPreview` debounced (counts
  lima/ámbar, lista expandible de inválidas con nº línea). `parseBulkUrls`
  puro testable: rechaza espacios explícitamente (Chromium los
  toleraba con %20), rechaza hosts sin TLD, autoañade https://.
  15 tests vitest (`b5ecb47`).
- Página `/leads/new` Server Component con header castellano +
  microcopy legal abajo (trazabilidad art. 6.1.f). Botón
  "+ Nuevo lead" outline ghost en cabecera de `/leads` junto al lima
  "+ Lanzar campaña" — jerarquía visual clara (`511fd4c`).
- Pulido: handler explícito 429 en bulk con copy específico, mobile
  verificado en viewport 375 (`72c751f`).
- `wcm leads create` CLI con XOR `--url`/`--bulk-file`. `CliApiError`
  ahora propaga `details` del envelope del API para que comandos
  reaccionen a casos específicos (ej. `existing_lead_id` en 409 single).
  8 tests pytest. Spec Playwright 8 tests (7 ejecutables + 1
  SSR-blocked) (`303bb80`).

### v0.10.0 — Rediseño `/settings` — cierre del ciclo completo — 2026-05-18

Última pantalla del rediseño. Distinta del resto: pantalla informativa
(no listado), sin KpiStrip/FilterChips. Confirmó la variación del
patrón ADR-036 para pantallas no-list.

- Endpoint `GET /api/v1/system/info` (admin/operator) con 6 campos de
  runtime (version, environment, python_version, alembic_revision,
  uptime_seconds, health summary). Reúsa los checkers de `/health/deep`
  para single source of truth. 6 tests pytest cubriendo shape, alembic
  null defensivo, overall degraded/fail, RBAC viewer 403, sin auth 401
  (commit `b44a99f`).
- 3 componentes presentacionales (`UserCard`, `SystemInfoPanel`,
  `OperationRunbook`) con el lenguaje visual denso del resto del
  dashboard (dl grid 2-col, fondo `wcm-secondary/30`, badges por
  rol/env/overall, formato de uptime escalable Nd Nh Nm). 13 tests
  vitest (`8936af0`).
- Refactor `page.tsx` a layout 2-col (Usuario+Sistema | Operación);
  título castellano "Ajustes" sustituyendo "Settings" (violación
  CLAUDE.md §3) (`67e07a1`).
- **Bug P0** eliminado: la mentira "UI de gestión: Fase 14" del
  placeholder original — Fase 14 pasó hace meses; misma clase que la
  "Fase 10" del diff que se limpió en v0.8.0. Guardia automática
  añadida en spec Playwright. README del dashboard también actualizado
  (otra mención "Fase 10" desfasada en la tabla de páginas) (`a7d4baa`).
- Spec Playwright 7 tests (4 ejecutables — más de los 2 habituales
  porque la guardia "no menciona Fase 14" y el runbook son
  client-side puros — + 3 SSR-blocked por WCM-021) (`69a1bce`).

### v0.9.0 — Rediseño `/errors` + `/residual-tasks` (sprint único) — 2026-05-18

Primer sprint que agrupa 2 pantallas porque ambas comparten patrón
exacto (lista plana de eventos del sistema con filtro por enum, sin
master-detail). Cierra todas las pantallas operativas del dashboard
salvo `/settings`.

- Endpoints `GET /api/v1/errors/stats` (8 buckets: total + 5 severities +
  distinct_components + last_critical_at) y `/residual-tasks/stats`
  (9 buckets: total + 5 status + blocking_go_live + distinct_projects +
  estimated_minutes_pending), ambos con ventana configurable
  (`since_hours` en errores) y RBAC (errors admin/operator,
  residuales any_user). 9 tests Python (`a146528`).
- `ErrorsTable` con SeverityBadge 5 colores + `ResidualTasksTable` con
  CategoryBadge ámbar para blocking_go_live y StatusPill castellana,
  responsive `hideUntil="md"`. 11 tests vitest (`e832b53`).
- Refactor páginas al patrón 5 bloques: KpiStrip (6 KPIs errors / 5
  residuales con tiempo pendiente formateado "Nh Mm") + FilterChips +
  empty states 2 ramas (systemEmpty lima vs filtro neutro)
  (`8106474`).
- Bloque 4 (responsive) verificado visualmente en 3 viewports — sin
  cambios necesarios; el KpiStrip wrappea en grid 2-3 cols sin
  overflow.
- Spec Playwright 12 tests (2 ejecutables + 10 skip por WCM-021),
  fixture base ampliado con handlers específicos /stats (`707bc95`).

### v0.8.0 — Rediseño `/projects/[id]` + 3 sub-páginas — 2026-05-18

- Endpoint `GET /api/v1/projects/{id}/summary` con agregados
  (lead_origin, phases counts, current_phase_name, residual counts)
  para evitar 3-4 fetches por sub-página (commit `64908c1`).
- 4 componentes shared en
  `apps/dashboard/src/app/(app)/projects/[id]/_components/`:
  `ProjectHeader`, `ProjectTabs` (Client), `PhaseProgressBar`,
  `ProjectPhasesTimeline` (`c3162d9`).
- Refactor de las 3 sub-páginas (overview, checklist, diff) para
  reusar `ProjectHeader` y fetch unificado (`c48f1ad`).
- Verificación visual con fixture de proyecto en desktop + mobile.
- Spec Playwright 14 specs (todas skipped por WCM-021 — el detalle
  depende 100% del SSR fetch) (`98b8591`).
- Bug P0 eliminado: copy "se implementa en Fase 10" del diff
  placeholder (Fase 10 pasó hace meses).
- Release v0.8.0.

### v0.7.0 — Rediseño `/projects` (listado) — 2026-05-18

- Endpoint `GET /api/v1/projects/stats` (commit `fbe56ec`).
- `ProjectsTable` con DiffIndicator coloreado por umbral (≥85/70/<70) +
  `KpiStrip` promovido a `apps/dashboard/src/components/` (`b1a5d3a`).
- Refactor `page.tsx` con KpiStrip + tabla + empty state lima (`d6b6730`).
- Filtros chips por status + `EmptyFilterResult` + responsive (`ec4001c`).
- Spec Playwright 2 ejecutables + 5 skipped (`9de2117`).
- Release `53288c2` → tag v0.7.0. CI verde.

### v0.6.0 + v0.6.1 — Consolidación prospección — 2026-05-18

- `/leads/[id]` full-page refactorizado a reusar `LeadDetailPane` del
  master-detail (`75d0879`). -135 líneas netas.
- `/campaigns` rediseñado completo en 5 bloques (`004801b` → `2ccf119`):
  endpoint `/runs` + `CampaignRunsTable` + `CampaignProgressCard`
  (polling) + LaunchForm horizontal con autocompletado + 2 empty states +
  spec Playwright.
- **Bug P0** eliminado: nota técnica obsoleta de `/campaigns`
  ("ProspectorAgent en stub · llega en Fase 9") — mentira desde v0.2.0.
- **v0.6.1 hotfix** (`2aefdca`): 2 `<a>` → `<Link>` en
  `EmptyHistorico`; `@next/next/no-html-link-for-pages` falló en CI.
  Memoria persistente actualizada con preflight incluyendo `pnpm lint`.

### v0.5.0 — Rediseño Panel/Overview — 2026-05-18

- Endpoint `GET /api/v1/audit-log` (lectura del audit canon que solo se
  escribía) (`c9879f8`).
- `ActivityFeed` + `OverviewKpiStrip` (`fafe46f`).
- Refactor `page.tsx` con feed agrupado por día + KPI strip
  (`0206041`).
- Filtros chips por action + responsive + onboarding card + header con
  badge env (`3028e1d`).
- Tests spec Playwright + visual baseline regenerada (`028990c`).
- Release `b929f74` → tag v0.5.0.

### v0.4.0 — Rediseño `/leads` master-detail — 2026-05-16

- Endpoint `GET /api/v1/leads/stats` (`7ef97a9`).
- 6 componentes presentacionales: ScorePanel, FingerprintList,
  EvidenceTable, ActivityTimeline, TopbarStats, FilterChips
  (`2121fb8`).
- Refactor `page.tsx` a master-detail con URL state `?selected=N`
  (`3aa419e`).
- Banner borrador, atajos teclado, responsive, acciones conectadas
  (`df43540`).
- Tests interactivos + e2e + visual baselines (`b2ad4e7`).
- Release `9e4a10c` → tag v0.4.0.

### v0.3.0 — `dev-status.sh` + venv.nosync iCloud fix — 2026-05-15

- Script `scripts/dev-status.sh` 3 modos (humano/quiet/json) para
  diagnosticar la stack local.
- Descubrimiento crítico: el bug WCM-008 (`.pth` ocultos) no era
  heurística macOS, era iCloud Drive sincronizando el Desktop. ADR-035
  supersede ADR-016. Solución: venv en `venv.nosync/` con symlink `venv`.
- Memoria persistente `feedback_macos_venv.md` actualizada.

### v0.2.x — Mejoras post-MVP (commits b5245e3, bdabdc0, 44620ad) — 2026-05-14

- Vista de progreso de campañas + i18n + paleta azul.
- Fix race condition POST /launch vs worker.
- best_builder prioriza cms > ecommerce > builder.

---

## Tareas completadas en la última sesión (Fase 15) — release v0.1.0

- [x] **Dependency audit**:
  - `pip-audit --skip-editable` → **0 vulnerabilidades** sobre 270+ deps Python.
  - `pnpm audit --prod`: 1 vuln moderate (`postcss<8.5.10` CVE GHSA-qx2v-qp2m-jg93 XSS via Stringify) → mitigada con `pnpm overrides` en root `package.json` forzando `postcss@^8.5.10`. Post-fix: **0 vulnerabilidades**.
- [x] **Security audit doc** `docs/security/audit-v0.1.0.md`: revisión manual de SQL/JWT/CORS/HMAC/secrets/Bash injection/PII en logs/RGPD. 0 findings bloqueantes.
- [x] **Rate limiting con slowapi** (ADR-033):
  - `apps/api/src/wcm_api/rate_limit.py` con limiter compartido.
  - Aplicado en: `/auth/login` 5/min, `/leads/{id}/outreach/compose` 10/min, `/leads/{id}/opt-out-url` 30/min, `/outreach/sequences/{id}/send` 30/min.
  - Handler `RateLimitExceeded` mapea a envelope JSON estándar (429 + `error.code=rate_limited`).
  - Limiter `enabled=False` por defecto en tests (autouse fixture en conftest) para no contaminar buckets entre tests; reactivado en `test_api_rate_limit.py`.
  - 3 tests nuevos: login 6º bloqueado, compose 11º bloqueado, /health sin límite.
- [x] **Performance baseline** `docs/performance.md`: SLOs para API/worker/dashboard + queries SQL + queries Prometheus + plan de tuning + pendientes WCM-018/019/020.
- [x] **CHANGELOG.md** estilo Keep-a-Changelog con todas las features v0.1.0 categorizadas (Added productos/apps/observabilidad/infra/tests/docs/decisions + Security + Known issues + Stack final + Equipo).
- [x] **`docs/release-v0.1.0.md`** con instrucciones paso a paso para push del repo (pre-flight check, opciones de creación repo, comandos exactos `git remote add`, `git tag`, `gh release create`, branch protection, secrets CI, equipo). El push es acción humana (irreversible) — todo preparado pero no ejecutado.
- [x] **ADR-033** (hardening philosophy: defensa en profundidad + audit programado + default seguro + trazabilidad). 33 ADRs en total.
- [x] **Tests**: 387 Python + 15 TS + 8 Playwright = **410 tests**. Coverage 74.8%. 0 regresiones.
- [x] **WCM-014..020** abiertos como roadmap post-v0.1.0 (idempotency keys, audit en CI, Secure+SameSite verificar en deploy, slowapi Redis storage para multi-nodo, Lighthouse CI, Grafana dashboards, alertas SLO).

## Tareas completadas en sesión anterior (Fase 14)

- [x] **`docs/arquitectura.md`** reescrito con 5 diagramas Mermaid:
  - Visión general productos (prospección + migración).
  - Topología single-server WHM (flowchart con systemd units + DB + externos).
  - Componentes lógicos del código (apps + packages + cli).
  - Flujo de migración con 15 fases del orchestrator + estados terminales.
  - Flujo de prospección con ciclo de vida del lead.
  - Modelo de datos ER (entidades principales).
  - Flujo de observabilidad (structlog → journald → Logtail; Prometheus → Grafana; Sentry).
  - Flujo de cumplimiento legal (descubrimiento → validador → composer → sender → opt-out).
  - Tabla de los **21 subagentes runtime** con estado real/stub.
- [x] **`docs/prospeccion.md`** completo en 10 secciones: modelo mental, lanzar campaña (dashboard + CLI), revisar leads, generar draft, aprobar/enviar, opt-outs (auto + manual + manual review), búsqueda semántica futura, auditoría, retención automática, métricas, troubleshooting.
- [x] **`docs/migracion.md`** completo en 13 secciones: modelo mental, crear proyecto, arrancar pipeline, **las 15 fases en tabla detallada**, seguimiento (dashboard + CLI + journalctl + Sentry), resume tras fallo, cancelar, troubleshooting por fase (scrape/extract/transpile/deploy/sync), criterios go-live ready, plugins instalados destino, interpretación visual diff con scores, rollback, métricas a vigilar.
- [x] **`docs/playbook-operativo.md`** con **10 runbooks INC-NN** (formato Síntoma → Diagnóstico → Acción → Verificación → Escalación): proyecto atascado, lead duplicado, solicitud RGPD no-email, brecha de seguridad, deploy fallido, worker no consume, Resend rebota >5%, /metrics expuesto, migración Alembic falló, ClickUp webhook no actualiza. Más sección de tareas recurrentes (rotación credenciales, backups, auditoría mensual audit_log).
- [x] **`docs/glossary.md`** nuevo con **40+ términos** alfabetizados: agent, asset, BricksPage, Celery, ContentBlock, embedding, fingerprinter, GDPR, hardening, idempotente, JWT, lead, LSSI-CE, opt_out_log, orchestrator, OutreachSequence/Send, pgvector, Playwright, Prometheus, resend, residual_task, scraped_page, structlog, systemd, transpiler, validador legal, webhook, WP-CLI, WPML... + referencias cruzadas.
- [x] **README.md** ampliado con sección **"Para operadores (quickstart)"**: primer login, lectura recomendada por rol (comercial/técnico), tabla de tareas habituales con comando exacto, dónde leer runbooks de incidentes.
- [x] Stubs antiguos de los 4 docs operativos sustituidos por versiones completas. Sin perder contenido valioso del bootstrap.

## Tareas completadas en sesión anterior (Fase 13)

- [x] **Playwright en dashboard** (`apps/dashboard/`):
  - `@playwright/test@^1.60` instalado como dev dep.
  - `playwright.config.ts` con `webServer: pnpm dev -p 3100`, locale es-ES, timezone Europe/Madrid, chromium project.
  - 4 specs en `tests/e2e/`: `login.spec.ts` (form + error toast), `leads.spec.ts` (lista + detalle), `projects.spec.ts` (lista + detalle + start), `visual.spec.ts` (regression overview + leads).
  - `fixtures/api-mocks.ts` con `installBaseMocks(page)` que intercepta `/api/v1/auth/*`, `/leads*`, `/projects*` con `page.route()`. Helper `loginViaCookie(page)` añade cookie wcm_session sin pasar por UI.
  - Vitest `exclude: ["tests/e2e/**"]` para no colisionar con Playwright.
  - Scripts: `e2e`, `e2e:ui`, `e2e:update-snapshots`.
  - 8 tests detectados con `playwright test --list`.
- [x] **E2E Python pipeline** (`tests/e2e/test_full_migration_pipeline.py`):
  - Fixture `stateful_session` en `tests/e2e/conftest.py` con storage por tipo de entidad + auto-id.
  - 5 tests cubren: migración mínima (5 fases + checklist), fallo en required → BLOCKED_HUMAN_INPUT, fallo en opcional → QA_FAILED (no bloquea), conditional skip por `condition_attr`, fingerprinter real contra HTML Wix fixture.
  - Stubs construyen `ScrapedPage`, `BricksPage`, `ResidualTask` reales del schema (no MagicMock).
- [x] **Coverage con `pytest-cov`**:
  - `pytest-cov>=5.0` añadido a dev deps de api y worker.
  - `pytest.ini` ampliado con `[coverage:run]` (source restringido a paquetes de producción + omits) y `[coverage:report]` (exclude_lines para TYPE_CHECKING, NotImplementedError, etc.).
  - **Coverage actual: 74.8%** (5899 statements, 1227 missed). Por encima del threshold 70%.
- [x] **CI matrix** en `.github/workflows/ci.yml`:
  - Python 3.13 + 3.14 (fail-fast: false).
  - Node 20 + 22 para dashboard.
  - Coverage exigido solo en Python 3.14 (`--cov-fail-under=70`). Artifact `coverage-xml` para integración con Codecov más adelante.
  - Job nuevo `e2e` que instala Playwright browsers + ejecuta tests headless (con `--ignore-snapshots` hasta que haya baselines x64).
- [x] **ADR-032** (estrategia e2e: Playwright + pipeline + visual regression + matrix).
- [x] **Total**: 384 Python + 15 TS + 8 Playwright = **407 tests**. Coverage 74.8%.

## Tareas completadas en sesión anterior (Fase 12)

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

## Release v0.1.0 CERRADO — 2026-05-14

Las 16 fases (0–15) están completadas y el MVP **está publicado en GitHub como repo público** en https://github.com/webcafeina/migrator. Release v0.1.0 visible en https://github.com/webcafeina/migrator/releases/tag/v0.1.0.

Pasos del `docs/release-v0.1.0.md` completados:
- ✅ Paso 1 (pre-flight checks: tests verdes, audit, sin secretos).
- ✅ Paso 2 (repo `webcafeina/migrator` creado en GitHub — público).
- ✅ Paso 3 (`git remote add origin` + `git branch -M main`).
- ✅ Paso 4 (primer `git push -u origin main` — 25 commits iniciales).
- ✅ Paso 5 (tag `v0.1.0` anclado a `adb95a7` + `git push origin v0.1.0`).
- ✅ Paso 6 (branch protection en `main` — hecho manualmente por el operador).
- ✅ Paso 8 (`gh release create v0.1.0 --title "v0.1.0 — primer MVP" --notes-file CHANGELOG.md` — release pública con todo el CHANGELOG).
- ✅ Paso 9 (CI verde en `main` tras 5 fixes iterativos sobre el primer run).
- ✅ Paso 11.1 (STATE.md actualizado con SHA del tag).
- ⏭️ Paso 10 (collaborators): saltado por decisión — sin roles individuales, el operador único gestiona el repo. Si en el futuro otros miembros del equipo necesitan permiso de escritura, se añaden como Collaborators 1-a-1 (repo público sin org-team).
- ⏭️ Paso 11.2/11.3: notificación al equipo + planificación de roadmap los hace el operador internamente.

Pendientes para cuando toque el primer deploy real al servidor WHM (no bloqueantes para el MVP):
- **Paso 7 del release-v0.1.0.md** (secrets GitHub Actions): `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY` en Settings → Secrets → Actions. Requiere servidor WHM provisionado primero.
- **Sudoers WHM** (`docs/despliegue.md` §4): `/etc/sudoers.d/wcm-deploy` para que `webcafeina` pueda reiniciar units sin password.

Post-release fix aplicado (commit `89c8469`):
- Refactor "equipo Webcafeína sin roles individuales": eliminadas todas las menciones a personas concretas en código, docs y subagentes. Convención: el equipo se trata como conjunto, sin assignees nominales.

Roadmap post-v0.1.0 (issues abiertos en `ISSUES.md`):
- WCM-011: revisión legal externa antes de outreach masivo.
- WCM-013: columna `retention_hold` para excepciones AEPD.
- WCM-014: idempotency keys en POST con side-effects.
- WCM-015: pip-audit + pnpm audit en CI.
- WCM-016: verificar `Secure` + `SameSite=Lax` cookie en deploy.
- WCM-017: slowapi storage Redis para multi-nodo.
- WCM-018: Lighthouse CI en Actions.
- WCM-019: Grafana dashboard SLOs.
- WCM-020: alertas en Grafana cuando p95 > critical.
- WCM-021: e2e con mock server real para Server Components (3 tests skipped).
- WCM-020: alertas en Grafana.

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

## Decisiones tomadas esta sesión (Fase 15)

- **Hardening filosofía formalizada en ADR-033**: defensa en profundidad (Nginx ACL → slowapi → Pydantic → RBAC → doble-check anti-spam → validador legal), audit programado (`docs/security/audit-vX.Y.Z.md` por release), default seguro (PII off, ACLs deny-all+allow, CORS lista explícita), trazabilidad sobre prevención (`audit_log` + `opt_out_log` permanente).
- **postcss override vía pnpm**: cuando una dep transitiva tiene vuln pero el árbol superior no se actualiza, `pnpm.overrides` en el root `package.json` es la mitigación cleanest. Documentado en audit doc.
- **slowapi `enabled=False` en tests**: tras varias horas intentando resetear el storage de slowapi entre tests sin éxito, decidimos desactivar el limiter por defecto en tests y reactivarlo solo en `test_api_rate_limit.py`. El handler `RateLimitExceeded` sigue funcionando, así que los tests del path de error tampoco rompen.
- **Push del repo a GitHub queda como acción humana** (no automatizable): la decisión sobre nombre/visibilidad/org requiere tu input. Tag local `v0.1.0` creado en `docs/release-v0.1.0.md` como instrucciones — NO ejecuté `git tag` ni `git push` para no crear estado inconsistente.
- **CHANGELOG en Keep-a-Changelog format**: categorías Added/Changed/Deprecated/Removed/Fixed/Security. Versionado SemVer. Cada release tendrá su entry con esta estructura.
- **3 niveles de severidad en dep audit**: high/critical parchar <72h, moderate parchar próximo release, low documentar+oportunista. Define la política de respuesta sin ambigüedad.

## Decisiones tomadas sesión anterior (Fase 14)

- **Docs operativos orientados a tareas, no a features**: en lugar de explicar "qué es ProspectorAgent", explico "cómo lanzar una campaña". El glosario cubre la parte conceptual; los docs de prospección y migración cubren la operativa.
- **Diagramas Mermaid en arquitectura.md** (no PNG): renderizables en GitHub directamente, fáciles de mantener en sync con el código. 8 diagramas distintos: productos / topología / componentes / flujo migración 15 fases / flujo prospección con ciclo de vida lead / ER datos / observabilidad / cumplimiento legal.
- **Playbook con formato INC-NN estricto**: cada incidente sigue Síntoma → Diagnóstico → Acción → Verificación → Escalación. Comandos copy-paste para SQL/bash. Esto reduce el time-to-resolution en producción.
- **Glosario alfabético con referencias cruzadas**: 40+ entradas. Permite a un nuevo del equipo entender el vocabulario sin abrir código.
- **README ya no menciona "para devs" vs "para ops"** explícitamente, pero la sección quickstart operador va arriba (los operadores no leen scroll largo).
- **Sin documentación generada automáticamente** (Sphinx, pdoc): mantenemos docs como markdown plano editado a mano. La autogenerada se vuelve obsoleta pronto y nadie la mira.
- **`docs/humanos/` sigue intocable** (regla #11): los docs que escribo son técnicos/operativos, no para el equipo humano comercial puro.

## Decisiones tomadas sesión anterior (Fase 13)

- **Dashboard e2e con API mockeada al 100%** (ADR-032): los Playwright tests usan `page.route()` para devolver fixtures controladas. Sin tocar el API real en ningún momento. Ventajas: tests deterministas, rápidos, no requieren Postgres ni Redis arrancados.
- **`webServer` de Playwright lanza `next dev -p 3100`**: puerto separado del dev humano (3000) para no chocar. Reuse del server existente en local, fresh start en CI.
- **Visual regression con tolerancia `maxDiffPixelRatio: 0.01`**: balance entre detectar cambios reales y no fallar por sub-pixel rendering differences entre ARM (dev mac) y x64 (CI).
- **CI omite visual specs hasta tener baselines x64** (`--ignore-snapshots`): regenerar con `pnpm e2e:update-snapshots` desde una run CI y commit los snapshots — ronda chicken-and-egg típica.
- **Pipeline e2e con clases reales del schema, NO MagicMock**: descubrimos que `MagicMock(__class__=MagicMock(__name__="X"))` no afecta a `type(obj).__name__`. Solución: usar `ScrapedPage`, `BricksPage`, `ResidualTask` reales en los stubs. Más realista y simplifica los asserts sobre `storage`.
- **Coverage source restringido**: `[coverage:run] source = packages/.../src + apps/.../src + cli/src` con `omit = */tests/*`. Mide solo código de producción; tests no inflan la métrica.
- **Threshold 70% mínimo**: estamos en 74.8%, así que hay margen. Configurado solo en la run Python 3.14 del CI (no contamos coverage doble por matrix).
- **Matrix Python 3.13 + 3.14**: detecta regresiones de versión cuando actualicemos el server. Si 3.13 empieza a fallar por sentence-transformers droppeando soporte, se decide en su momento.

## Decisiones tomadas sesión anterior (Fase 12)

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

**Lectura obligatoria al arrancar**: este fichero + `CLAUDE.md` + las
entradas correspondientes de `MEMORY.md` (auto-memoria persistente).

**Reglas operativas que ahora viven en memoria** (no hace falta releer):
- Preflight de release: `git status` + `pytest` + `ruff` + `tsc` + `vitest`
  + **`pnpm lint`** (ver `feedback_release_preflight.md` — añadido tras
  v0.6.0→v0.6.1 hotfix). `next lint` NO se ejecuta con tsc/vitest.
- macOS venv: vive en `venv.nosync/` con symlink `venv` para evitar el
  bug iCloud (ADR-035). NO recrear como `.venv/`.
- `docs/humanos/` intocable (regla #11 CLAUDE.md).
- Limpiar `.next/cache` antes de demo visual; `Cmd+Shift+R` en navegador.
- Periódicamente borrar `apps/dashboard/.next/types/* [N]*.ts` (iCloud
  duplica) — WCM-038.

**Test suite actual a 2026-05-18 (v0.7.0)**:
- 453 pytest (era 387 en MVP; +66 entre rediseños).
- 92 vitest passing + 3 skipped React 19 (era 15; +77).
- 17 Playwright ejecutables + 28 skipped por WCM-021 (MSW node)
  (era 8; +9 ejecutables, +28 skipped).
- Para correr todo:
  ```bash
  set -a && source .env && set +a && venv.nosync/bin/pytest -q
  cd apps/dashboard && PATH="/opt/homebrew/opt/node@22/bin:$PATH" pnpm exec vitest run
  PATH="/opt/homebrew/opt/node@22/bin:$PATH" pnpm exec playwright test
  ```

**Siguiente trabajo natural**: extender rediseño a las 4 pantallas
restantes (ver tabla arriba):
1. WCM-034 (P1) — `/projects/[id]` + sub-páginas (`checklist`, `diff`).
   El más grande de los pendientes: 3-4 sub-páginas anidadas.
2. WCM-035 (P2) — `/errors` y `/residual-tasks` (agrupable en un release).
3. WCM-021 (P2) — MSW node desbloquea 28 specs Playwright skipped.
4. WCM-036 (P3) — 3 vitest skipped por React 19 + `startTransition(async)`.

**Issues abiertos pre-rediseño que siguen vigentes** (originales del MVP):
- WCM-001 (P0) export real Bricks Builder.
- WCM-003 (P1) URLs reales por builder para calibrar scraper.
- WCM-005 (P2) lista ClickUp por defecto.
- WCM-011 (P1) revisión legal externa de prospección.
- WCM-029, WCM-030 (P2) detalles `.env.example` + greenlet dep.
