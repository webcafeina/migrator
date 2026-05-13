# Migración — guía del operador

Cómo lanzar una migración Wix/Hostinger AI/Webflow → WordPress + Bricks. Pensado para el equipo técnico de Webcafeína.

---

## 0. Modelo mental

Un **proyecto** representa una migración. El operador:

1. **Crea** el proyecto con `--source URL --client NAME` y flags (`--ecommerce`, `--multilang`).
2. **Lanza** el pipeline (`start`). El orchestrator ejecuta hasta 15 fases en orden.
3. **Espera** updates (dashboard timeline o `wcm projects status <id>`).
4. **Revisa** el resultado: visual diff + checklist residual.
5. **Coordina** con el equipo de ClickUp para las tareas no automatizables.

Estados del proyecto:

```
QUEUED → RUNNING → COMPLETED       (todo OK)
                ↘ QA_FAILED         (fase opcional falló, revisión humana)
                ↘ BLOCKED_HUMAN_INPUT (fase requerida falló)
                ↘ CANCELLED         (operador canceló)
```

---

## 1. Crear un proyecto

### CLI

```bash
wcm projects new \
    --source "https://barpepe.es" \
    --client "Bar Pepe S.L." \
    --target "barpepe-wp.localhost" \
    --ecommerce false \
    --multilang false
```

Devuelve `project_id`. Lo necesitas para todo lo demás.

### Dashboard

`/projects` → botón **"Nuevo proyecto"** → formulario.

### Qué se crea en BD

- Row en `projects` con `status=QUEUED`.
- Row en `audit_log` con `CREATE entity=project`.

No se ejecuta nada todavía. El pipeline empieza con `start`.

---

## 2. Arrancar el pipeline

### CLI

```bash
wcm projects start 42
```

### Dashboard

`/projects/42` → botón **"Start"**.

### Qué pasa

Encola `wcm.orchestrator.run_project` con `project_id=42`. El worker:

1. Marca `projects.status = RUNNING`, `started_at = now`.
2. Recorre las 15 fases del `_DEFAULT_PHASES` (ver `apps/worker/.../pipeline.py`).
3. Por cada fase:
   - Persiste un `project_phases` row con `status=RUNNING`.
   - Ejecuta el subagente.
   - Persiste resultado o error con `status=COMPLETED/FAILED/SKIPPED`.
4. Al final marca `projects.status = COMPLETED | QA_FAILED | BLOCKED_HUMAN_INPUT`.

---

## 3. Las 15 fases en detalle

| # | Fase | Agente | Required | Condicional | Qué hace |
|---|---|---|---|---|---|
| 1 | scrape_origin | ScraperOriginAgent | sí | — | BFS interno con httpx; persiste `ScrapedPage` por URL visitada |
| 2 | extract_content | ContentExtractorAgent | sí | — | Aplica extractor (Wix/Hostinger/Webflow) según `builder_source`; persiste `ContentBlock` |
| 3 | preserve_seo | SeoPreserverAgent | sí | — | Extrae title/meta/OG/canonical/hreflang/JSON-LD/h1; persiste warnings |
| 4 | optimize_assets | AssetOptimizerAgent | no | — | Descarga assets, Pillow→WebP q82, sube a R2 (si configurado) |
| 5 | detect_multilang | MultilangHandlerAgent | sí | — | `<html lang>` + count por idioma |
| 6 | transpile_bricks | BricksTranspilerAgent | sí | — | HTML/CSS → Bricks JSON (ver `packages/bricks-transpiler`) |
| 7 | deploy_wp | WpDeployerAgent | sí | — | REST upsert + WP-CLI/SSH `bricks_import_content` |
| 8 | migrate_woo | WooMigratorAgent | no | `has_ecommerce` | (post-MVP) productos + variaciones + categorías |
| 9 | configure_wpml | WpmlConfiguratorAgent | no | `is_multilang` | (post-MVP) configura WPML + traduce |
| 10 | rebuild_forms | FormsRebuilderAgent | no | — | (post-MVP) reconstruye Gravity Forms desde el original |
| 11 | visual_diff | VisualDiffAgent | no | — | (post-MVP) pixelmatch contra screenshots origen |
| 12 | qa | QaRunnerAgent | no | — | (post-MVP) batería de checks (broken links, perf, a11y) |
| 13 | generate_checklist | ChecklistGeneratorAgent | no | — | (post-MVP) crea `ResidualTask` por gap detectado |
| 14 | sync_clickup | ClickupSyncerAgent | no | — | Crea/actualiza tareas ClickUp con `clickup_task_id` |
| 15 | notify | ResendNotifierAgent | no | — | Email a Nacho/operador asignado |

**"Required"** significa: si falla, el proyecto pasa a `BLOCKED_HUMAN_INPUT` y el pipeline para.
**"No required"** que falla: el proyecto se completa pero queda como `QA_FAILED` (revisión recomendada).

---

## 4. Seguir el progreso

### Dashboard

`/projects/42` muestra:
- **Status badge** (queued/running/completed/qa_failed/blocked).
- **Configuración**: source, target, builder, ecommerce, multilang.
- **Timeline de fases**: una línea por `project_phases`, con badge de status y timestamp.
- **Botones**: Start (si queued), Resume (si blocked), Cancel.
- **Visual diff score**: si la fase visual_diff corrió.

### CLI

```bash
wcm projects get 42                # detalle completo JSON
wcm projects status 42             # solo status + última fase
wcm projects phases 42             # listado de project_phases
```

### Logs

```bash
# En el servidor
journalctl -u wcm-worker -f --since '5 minutes ago' | grep "project_id=42"
```

### Sentry

Errores con stack trace tagueados por `component=worker` y `phase=<phase_name>`.

---

## 5. Resume tras fallo

Si el proyecto está `BLOCKED_HUMAN_INPUT`:

1. Identifica la fase fallida en el timeline.
2. Resuelve la causa (ver §7 troubleshooting).
3. Resume:

```bash
wcm projects resume 42
```

O dashboard → botón **Resume**.

El orchestrator arranca desde la **primera fase no completada** (no re-ejecuta lo que ya hizo). Esto es seguro porque cada fase es idempotente (escribe `ON CONFLICT DO NOTHING` o equivalente).

---

## 6. Cancelar

Si decides abortar:

```bash
wcm projects cancel 42 --reason "Cliente no firma contrato"
```

Marca `status=CANCELLED` + AuditLog. No borra los datos generados — quedan para análisis o resume futuro.

---

## 7. Troubleshooting por fase

### scrape_origin
| Síntoma | Causa típica | Acción |
|---|---|---|
| 0 páginas scrapeadas | Wix bloquea bots / robots.txt | Configurar Bright Data proxy (`BRIGHTDATA_*` en `.env`). Re-resume. |
| ScrapedPage solo con la home | `<a href>` internos malformados | Revisar extractor del builder origen — algunos JS frameworks no renderizan los enlaces en HTML inicial |
| Timeout 30s | Site lento | Subir `SCRAPER_DEFAULT_TIMEOUT_MS` en `.env`. Restart worker. |

### extract_content
| Síntoma | Causa | Acción |
|---|---|---|
| Muchos bloques `unknown` | El extractor no reconoce el tipo de bloque | Anotar la URL + screenshot, crear issue WCM-NNN, mientras: el checklist los listará como residuales |
| Imágenes sin alt | El builder origen no las tenía | Tarea residual automática |

### transpile_bricks
| Síntoma | Causa | Acción |
|---|---|---|
| `BricksTranspilerError: schema mismatch` | Bloque no mapeado en `packages/bricks-transpiler` | Ver detalle en el error_log. Añadir mapper o marcar bloque como unsupported (se vuelve residual) |
| BricksPage vacío | extract_content devolvió 0 bloques | Revisar fase 2 |

### deploy_wp
| Síntoma | Causa | Acción |
|---|---|---|
| `WpAuthError` | App password incorrecto | Regenerar en WP admin → Users → Application Passwords. Actualizar `WP_DEFAULT_REST_APP_PASSWORD` |
| `WpCliSshError: command not found` | wp-cli no en PATH del SSH user | Configurar `WP_DEFAULT_WPCLI_PATH` con ruta absoluta |
| Subida lenta (>10 min) | REST tiene rate limit por defecto | Subir `WP_REST_BATCH_SIZE` o usar WP-CLI bulk (más rápido) |
| WP destino devuelve 500 | Plugin incompatible | Mirar `/wp-content/debug.log` en el sandbox; deshabilitar plugin sospechoso |

### sync_clickup
| Síntoma | Causa | Acción |
|---|---|---|
| `ClickUp[401]` | Token expirado o inválido | Renovar en ClickUp settings → Apps → tu token personal |
| Tareas duplicadas en ClickUp | Sync se ejecutó dos veces con `clickup_task_id` no persistido | Borrar duplicadas manualmente; el dedupe es por columna `residual_tasks.clickup_task_id` |

---

## 8. Criterios de "go-live ready"

Para considerar una migración lista para apuntar DNS:

- [ ] `project.status = COMPLETED` (o `QA_FAILED` con todas las críticas resueltas).
- [ ] Visual diff promedio ≥ **0.85** en home, ≥ **0.80** en al menos 80% de páginas internas (`project.visual_diff_avg_score`).
- [ ] Todos los `residual_tasks` con `category=BLOCKING_GO_LIVE` cerrados (`status=DONE`).
- [ ] `residual_tasks` con `category=CLIENT_CONFIG` revisados (DNS, email transaccional, analytics).
- [ ] SEO redirects 301 generados y revisados (`/seo-redirects` endpoint).
- [ ] QA runner sin críticos.
- [ ] Backup del sitio origen tomado (para rollback si el cliente se arrepiente).

---

## 9. Plugins instalados en destino

**Siempre**:
- Bricks Builder (tema)
- Yoast SEO
- Redirection
- Gravity Forms
- WP Rocket (o cache equivalente)
- Google Site Kit
- Advanced Custom Fields (free)

**Condicional**:
- WPML — si `is_multilang=true`
- WooCommerce + add-ons → si `has_ecommerce=true`

Lista exacta y versiones en `packages/wp-client/src/wcm_wp_client/plugins.py`.

---

## 10. Visual diff: interpretación

`apps/worker/.../agents/visual_diff.py` (post-MVP) hará `pixelmatch` página a página:

| Score | Interpretación | Acción |
|---|---|---|
| ≥ 0.95 | Migración pixel-perfect | Aprobar |
| 0.85-0.95 | Diferencias mínimas (fonts, antialiasing) | Revisar visualmente, normalmente OK |
| 0.70-0.85 | Diferencias notables (layout, colores) | Identificar bloque problemático en `bricks_pages` |
| < 0.70 | Migración rota | Resume con fix del bloque |

El threshold mínimo es `VISUAL_DIFF_THRESHOLD=0.85` en `.env`. Por debajo, `qa_runner` marca el proyecto como `QA_FAILED`.

---

## 11. Rollback

Si el cliente decide no migrar tras ver staging:

1. `wcm projects cancel <id> --reason "Cliente no migra"`
2. El sandbox WP destino se puede borrar manualmente.
3. Los datos en `projects` quedan para auditoría.

Si ya se cambió el DNS y se quiere rollback:

1. Operador apunta DNS al sitio origen otra vez (TTL <5 min recomendado durante migraciones).
2. Marca proyecto `CANCELLED`.
3. Documenta el incidente en `apps/api/legal/registro_incidentes.md`.

---

## 12. Métricas a vigilar

| Métrica | Dónde | Healthy range |
|---|---|---|
| Tiempo total migración 10-páginas | journalctl + grep duration | < 90 min |
| Visual diff promedio | `/projects/{id}` dashboard | ≥ 0.85 |
| Residuales por proyecto | `residual_tasks` count | < 15 para web corporativa típica |
| Failure rate por fase | `wcm_celery_tasks_total{status="failure"}` Prometheus | < 5% sobre runs últimas 24h |
| Latencia p95 fase transpile_bricks | `wcm_celery_task_duration_seconds{task="transpile_bricks"}` | < 60s para web 10 páginas |

---

## 13. Para futuras fases

- Post-MVP: visual diff real con `pixelmatch` (Fase 13+ del backlog).
- Post-MVP: woo-migrator productos.
- Post-MVP: wpml-configurator.
- Post-MVP: forms-rebuilder con detección de campos Gravity Forms.
