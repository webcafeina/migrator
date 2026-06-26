# Handoff sesión v0.29.0 — pausa 2026-06-26

Documento único para retomar la sesión donde quedó. Léeme primero al volver al
proyecto, después `STATE.md` para contexto histórico.

## Estado del código

- **Commit actual**: `912fcd7` (`feat(v0.29.0): BriefSectionAggregator (B0-B5.5) — fix WCM-053`)
- **Rama**: `main`
- **Push**: NO (commit local, repo remoto sin actualizar)
- **Tree**: limpio antes de iniciar este handoff. Después de generar este
  documento + actualizar STATE.md/memory aparecerán cambios sin commitear que
  el operador puede commitear cuando quiera (`docs/handoff-v0.29.0-pause.md`,
  `STATE.md`, files de memory en `~/.claude/`).

### Archivos clave del sprint v0.29.0 (todos en `912fcd7`)

- `packages/db-schema/alembic/versions/0024_v029_brief_aggregation.py`
- `packages/db-schema/src/wcm_db/models/projects.py` (+2 columnas)
- `packages/bricks-transpiler/src/wcm_bricks_transpiler/redesign/semantic_taxonomy.py`
- `apps/worker/src/wcm_worker/integrations/openai_client.py` (+`TOOL_AGGREGATE_SECTIONS` + `aggregate_page_sections()`)
- `apps/worker/src/wcm_worker/agents/brief_aggregator.py`
- `apps/worker/src/wcm_worker/errors.py` (+`BriefAggregatorError`)
- `apps/worker/src/wcm_worker/pipeline.py` (fase `brief_aggregate` posición 6)
- `apps/dashboard/src/app/(app)/projects/new/_components/aggregation-cost-dialog.tsx`
- `apps/dashboard/src/app/(app)/projects/new/_components/new-project-wizard.tsx`

## Estado de los entornos

| Recurso | Estado |
|---|---|
| BD local (Postgres) | Alembic head `0024_v029_brief_aggregation`. **Sin proyectos** (`SELECT * FROM projects` vacío) |
| R2 (Cloudflare) | Vacío bajo prefix `projects/` |
| WP destino | 0 pages, 0 media |
| Redis (Celery) | Cola vacía, sin tasks pendientes |
| API uvicorn (8000) | Apagado |
| Worker celery | Apagado |
| Dashboard Next.js (3000) | Apagado. Nota: hay un proceso `node` externo (PID variable) escuchando en `*:hbci` (= puerto 3000 en macOS) — coexistió sin conflicto en la sesión previa; si Next falla al arrancar con `EADDRINUSE`, identificar con `lsof -i :3000` y matar el ocupante |

## Cómo relevantar el stack para retomar

Recordatorios cruciales:
- venv es **`venv.nosync`** con symlink `venv` (bug iCloud — NO recrear como `.venv/`)
- Dashboard cuelga si `SENTRY_DSN_DASHBOARD` está set — exportar vacío
- Worker en macOS necesita `--pool=threads` (segfault con prefork, WCM-033)

```bash
cd /Users/alvaro/Desktop/webcafeina-migrator
source venv/bin/activate
set -a; source .env; set +a

# Terminal 1 — API
python -m uvicorn wcm_api.main:app --host 127.0.0.1 --port 8000 --log-level info

# Terminal 2 — Worker (en otra ventana, con venv + env)
celery -A wcm_worker.celery_app:celery_app worker \
  --loglevel=info --pool=threads --concurrency=2 \
  -Q default,migration

# Terminal 3 — Dashboard (en otra ventana)
cd apps/dashboard
SENTRY_DSN_DASHBOARD= NEXT_PUBLIC_SENTRY_DSN= pnpm dev
```

Smoke check:
- `curl http://127.0.0.1:8000/health` → `{"status":"ok"}`
- `curl -sI http://127.0.0.1:3000` → `307 Temporary Redirect → /login`
- `grep -c 'celery@' /tmp/wcm-worker.log` ≥ 1

## Próxima acción concreta: B6 — E2E manual mariya.design

### Flujo del wizard (lanzado por operador desde dashboard)

1. `http://127.0.0.1:3000/login` → entrar
2. `/projects/new` → 6 pasos:
   - **Paso 1 Origen**: URL `https://mariya.design`, client `Mariya Design`, builder lo que detecte
   - **Paso 2 Negocio**: vacío (BriefGenerator auto-detecta) o `sector=portfolio`, `tone=premium`
   - **Paso 3 Diseño**: **Hybrid** (sin seleccionar templates/ai explícito) — el flujo nuevo se valida mejor aquí. Alternativa de menor riesgo: "Templates puro"
   - **Paso 4 Destino**: WP de pruebas (`WP_DEFAULT_SITE_URL` del `.env`)
   - **Paso 5 Features**: input nuevo "Cap de páginas" — dejar en `50` (default)
   - **Paso 6 Preflight**: "Crear proyecto y ejecutar preflight"
3. Al pulsar **"Crear y arrancar pipeline"**: como `cap=50 > 20`, abre el modal nuevo con coste estimado ≈ $0.50. Confirmar.

### Qué eventos esperar del worker (criterios de éxito v0.29.0)

| Fase | Comportamiento esperado |
|---|---|
| `scrape_origin` | ~50 páginas scrapeadas |
| `extract_content` | ~1500 `content_blocks` (caso mariya conocido) |
| `brief_generator` | `brief_json.pages[].sections[]` con tipos planos (heading/text/image/grid/...) |
| `brief_aggregate` | **El nuevo**. Reduce N_sections de ~1550 → ~50-100. `Project.brief_aggregation_cost_usd ≈ $0.30-0.80`. Cada page con `aggregated_at` y `aggregation_method=llm|cache|fastpath` |
| `redesign_templates` | Ahora debería matchear `>>0.6%` (criterio aceptación: `≥80%`). Residuals esperados `≤10%` |
| `redesign_images` | gpt-image-2 rellena slots vacíos según `image_generation_budget_usd` (default 1.00 USD) |
| `bricks_adapt` | Adapter determinista — sin advertencias críticas |
| `visual_quality` | Score Playwright por página. Threshold env-override |

### Lanzar monitor durante el E2E

```bash
tail -F /tmp/wcm-worker.log | grep -E --line-buffered \
  "phase_completed|phase_failed|phase_skipped|brief_aggregator_|aggregator_|template_skipped|template_not_found|ERROR|Traceback|FAILED"
```

### Cleanup tras E2E si falla / si necesitas re-ejecutar

```bash
source venv/bin/activate
python <<'PY'
from dotenv import load_dotenv; load_dotenv('.env')
import os, psycopg
url = os.environ['DATABASE_URL'].replace('+asyncpg','').replace('postgresql+psycopg','postgresql')
with psycopg.connect(url, autocommit=True) as conn, conn.cursor() as cur:
    cur.execute("SELECT id, source_url FROM projects ORDER BY id DESC LIMIT 5")
    for r in cur.fetchall(): print(r)
PY
# Borrar proyecto problemático (CASCADE):
#   DELETE FROM projects WHERE id=<id>
# Limpiar R2 + WP destino con el script de cleanup ya documentado en sesión previa
```

## B7 — Release v0.29.0 (cuando B6 valide)

Checklist preflight (orden crítico):
1. `git status` limpio
2. `ruff check apps packages cli scripts`
3. `pytest packages -q`
4. `pytest apps/worker/tests/unit -q --ignore=apps/worker/tests/unit/test_agents_stubs.py --ignore=apps/worker/tests/unit/test_checklist_generator_pdf.py --ignore=apps/worker/tests/unit/test_resend_notifier.py` (excluir tests con segfault flake conocido)
5. `cd apps/dashboard && pnpm type-check && pnpm lint && pnpm exec vitest run`
6. CHANGELOG cubriendo **v0.28.0 + v0.29.0** (v0.28.0 no se releaseó, sus cambios entran en este release también)
7. ADR-059 — `BriefSectionAggregator + modal coste wizard`
8. Bump SemVer en `pyproject.toml` + `package.json` + `apps/dashboard/package.json`
9. STATE.md cabecera (mover v0.29.0 de "en curso" a "publicada", remover sección v0.27.0 como "última")
10. `git commit -m "chore(release): v0.29.0"`
11. `git tag v0.29.0`
12. `git push origin main --tags`
13. `gh release create v0.29.0 --title "v0.29.0 — BriefSectionAggregator" --notes-file CHANGELOG-v0.29.0.md` (release público obligatorio)

## Tasks abiertas tras esta pausa

- **#225** — `v0.29.0 B6 — E2E manual con cliente real (re-ejecutar mariya.design)` — pending
- **#226** — `v0.29.0 B7 — Release v0.29.0` — pending
- **WCM-053** (P0) — bug raíz del sprint, **resolución pendiente de validar en B6**
- **WCM-039** (P1) — distributed lock, mitigado, diferido

## Riesgos conocidos para B6

1. **Coste real superior a estimado**: el modal estima `$0.01/página` pero gpt-5.5 puede ser más caro si páginas son grandes. Monitor: cortar si `brief_aggregation_cost_usd > $2`
2. **LLM emite tipos fuera de taxonomía**: el aggregator emite warning y deja la página sin agregar — los residuals aumentarán. Si pasa en >20% de páginas, ajustar `SYSTEM_PROMPT_AGGREGATE_SECTIONS`
3. **Cache lookup falla en re-run**: si cambia el orden de claves en blocks, el SHA cambia y se re-paga. Verificado con `test_compute_blocks_sha_estable_e_independiente_del_orden_de_keys` pero ojo en BD real
4. **Hybrid sigue Frankenstein** aunque matches mejoren — esto es riesgo arquitectónico v0.30.0+, no de este sprint. Si pasa, recomendar al operador "Templates puro" para el siguiente E2E
