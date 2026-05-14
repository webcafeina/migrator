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
- **Estado**: OPEN (mitigado con workaround)
- **Contexto**: macOS marca como hidden los archivos dentro de directorios `.dotted/`. Python 3.14 ahora skipea `.pth` files con flag hidden. Sin fix, `pip install -e` parece funcionar pero los paquetes no son importables.
- **Acción**: Ejecutar `bash scripts/fix-venv-hidden-pth.sh` tras cualquier `pip install`. Si upstream Python revierte el cambio o setuptools usa naming sin doble underscore, retirar el workaround.
- **Dueño**: técnico — monitorear changelogs de Python 3.14 y setuptools.
- **Ver**: ADR-016.

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
- **Tipo**: bug / **Fase**: 9 (descubierto en dev-local 2026-05-14) / **Prioridad**: **P0**
- **Estado**: OPEN
- **Contexto**: la task `wcm.prospector.run_campaign` solo crea leads `DISCOVERED`. NO encola fingerprint ni enrich después. En producción los leads se quedan colgados sin contacto/score. El operador tendría que hacerlo manual lead-a-lead.
- **Acción**: tras `_upsert_lead`, encolar `wcm.fingerprinter.run.delay(lead_id)`. El fingerprinter task encadena enrich (ver WCM-027). Test e2e que verifique status `ENRICHED` tras campaña.

---

### WCM-027 (CRÍTICO) — Falta task Celery + endpoint + CLI para enrich
- **Tipo**: feature / **Fase**: 9 (descubierto en dev-local 2026-05-14) / **Prioridad**: **P0**
- **Estado**: OPEN
- **Contexto**: existe `EnricherAgent` pero **no se expone**: no hay task Celery `wcm.enricher.run`, ni endpoint API `/leads/{id}/enrich`, ni comando CLI `wcm leads enrich`. Solo se puede usar via script Python ad-hoc.
- **Acción**:
  - `apps/worker/src/wcm_worker/tasks/enricher.py` con `@celery_app.task(name="wcm.enricher.run")`.
  - `apps/api/src/wcm_api/routers/leads.py` añadir `POST /leads/{id}/enrich`.
  - `cli/src/wcm_cli/commands/leads.py` añadir `wcm leads enrich <id>`.
  - El fingerprinter task lo encola automáticamente tras fingerprint.

---

### WCM-028 — Warning estático obsoleto en `wcm campaigns launch`
- **Tipo**: bug / **Fase**: 7 (CLI) / **Prioridad**: P3
- **Estado**: OPEN
- **Contexto**: el comando imprime `⚠ ProspectorAgent es stub en Fase 6. Implementación real en Fase 9.` — texto hardcodeado obsoleto desde que ProspectorAgent es real en Fase 9.
- **Acción**: eliminar el `typer.echo` en `cli/src/wcm_cli/commands/campaigns.py`.

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

## Plantilla para nuevos issues

```
### WCM-NNN — Título corto
- **Tipo**: feature|bug|chore|docs|test|infra / **Fase**: N / **Prioridad**: P0|P1|P2|P3
- **Estado**: OPEN
- **Contexto**: ...
- **Acción**: ...
- **Dueño**: humano | técnico | a asignar
```
