# apps/worker

Celery worker que ejecuta los **20 subagentes** del producto Webcafeína Migrator.

## Estado

Materializado en **Fase 6**. Pipeline e2e funcional en modo MVP:
- **8 subagentes REAL** (envuelven los paquetes ya construidos)
- **11 subagentes STUB** con `NotImplementedError` + mensaje accionable
- **Orchestrator** state machine que recorre las fases del pipeline
- **4 Celery tasks** que matchean los `send_task` del API

## Arrancar el worker

```bash
# Asegurar venv + dependencias + Redis arriba
source .venv/bin/activate
set -a; source .env; set +a

# Levantar broker (Redis) y luego el worker:
redis-server  # o brew services start redis

celery -A wcm_worker.celery_app worker --loglevel=info --concurrency=4 -Q webcafeina
```

## Subagentes implementados

| Subagente | Estado | Notas |
|---|---|---|
| `FingerprinterAgent` | ✅ REAL | Usa `wcm_scraper_core.fingerprint`. Niveles 1-3 (sin browser). |
| `EnricherAgent` | ✅ REAL | Regex emails (anti-placeholder), teléfonos ES, redes sociales. |
| `ScraperOriginAgent` | ✅ REAL | BFS interno con httpx + BeautifulSoup. Persiste scraped_pages. |
| `ContentExtractorAgent` | ✅ REAL | Aplica `wcm_scraper_core.extractors` según `builder_source`. |
| `SeoPreserverAgent` | ✅ REAL | Extrae title/meta/OG/canonical/hreflang/JSON-LD/h1. Avisos por página. |
| `MultilangHandlerAgent` | ✅ REAL | Detección por `<html lang>` con contador por idioma. |
| `BricksTranspilerAgent` | ✅ REAL | Usa `wcm_bricks_transpiler.transpile_page` + validator. |
| `WpDeployerAgent` | ✅ REAL | Usa `wcm_wp_client` (REST upsert + WP-CLI para post meta). |
| `ProspectorAgent` | 🟡 STUB | Fase 9 — Google Maps + directory-scraper + dorks. |
| `OutreachComposerAgent` | 🟡 STUB | Fase 9 — plantillas LSSI-CE compliant. |
| `AssetOptimizerAgent` | 🟡 STUB | Fase 10 — pipeline imágenes + R2. |
| `WooMigratorAgent` | 🟡 STUB | Condicional `has_ecommerce`. Skill `wp-rest-bulk`. |
| `WpmlConfiguratorAgent` | 🟡 STUB | Condicional `is_multilang`. |
| `FormsRebuilderAgent` | 🟡 STUB | Gravity Forms via REST. |
| `VisualDiffAgent` | 🟡 STUB | Playwright + pixelmatch. |
| `ChecklistGeneratorAgent` | 🟡 STUB | WeasyPrint PDF, Fase 10/14. |
| `QaRunnerAgent` | 🟡 STUB | Lighthouse + W3C validator + link check. |
| `ClickupSyncerAgent` | 🟡 STUB | Fase 10 — sync residual_tasks ↔ ClickUp. |
| `ResendNotifierAgent` | 🟡 STUB | Fase 10 — Resend email transaccional. |

## Pipeline de migración (orchestrator)

```
scrape_origin → extract_content → preserve_seo →
  optimize_assets [opcional] → detect_multilang →
  transpile_bricks → deploy_wp →
  migrate_woo [si has_ecommerce] → configure_wpml [si is_multilang] →
  rebuild_forms [opcional] → visual_diff [opcional] → qa [opcional] →
  generate_checklist [opcional] → sync_clickup [opcional] → notify [opcional]
```

Cada fase persiste su estado en `project_phases` (running/completed/skipped/failed).
Si una fase **required** falla, el proyecto pasa a `BLOCKED_HUMAN_INPUT` y el pipeline se detiene; las opcionales registran el fallo pero continúan.

`AgentNotImplementedError` (los stubs) se trata como skip — el pipeline avanza.

## Celery tasks registradas

Cada una matchea un `send_task(name=...)` del API:

| Task name | Encolada por | Implementación |
|---|---|---|
| `wcm.orchestrator.run_project` | `POST /projects/{id}/start` | `tasks/orchestrator.py` → `Orchestrator` |
| `wcm.fingerprinter.run` | `POST /leads/{id}/refingerprint` | `tasks/fingerprinter.py` → `FingerprinterAgent` |
| `wcm.prospector.run_campaign` | `POST /campaigns/launch` | `tasks/prospector.py` (stub, devuelve `not_implemented`) |
| `wcm.clickup.sync_residuals` | `PATCH /residual-tasks/{id}/status` | `tasks/clickup.py` (stub) |

## Tests

```bash
# Tests unit sin DB ni Redis (28 tests):
pytest apps/worker -q

# Total repo:
set -a; source .env; set +a
pytest packages apps -q
```

Fixtures clave:
- `fake_session` — `Session` mockeada (sync, no async — el worker es sync)
- `CELERY_TASK_ALWAYS_EAGER=true` en tests para que `.apply()` no requiera broker

## ADRs relacionados

- ADR-020 — Subagentes runtime en `apps/worker/agents/` (distintos de los descriptors `.claude/agents/`)
