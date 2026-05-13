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
- **Dueño**: humano (Álvaro o Samuel).

### WCM-002 — Confirmar datos legales de Webcafeína S.L.
- **Tipo**: docs / **Fase**: 9 / **Prioridad**: P1
- **Estado**: DONE (cerrado en sesión Fase 9, 2026-05-13)
- **Resolución**: CIF B10463990, dirección Santa Cristina s/n – Edificio Embarcadero 10195 Cáceres, URL privacidad https://webcafeina.com/politica-privacidad/ persistidos en `.env` + `apps/api/legal/tratamiento_datos_prospeccion.md`.

### WCM-003 — Calibrar skills de extracción con webs reales
- **Tipo**: chore / **Fase**: 3 / **Prioridad**: P1
- **Estado**: OPEN
- **Contexto**: Los skills `wix-extraction`, `hostinger-ai-extraction` y `webflow-extraction` parten con patrones documentados teóricos. Requieren validación con al menos 3 webs reales por constructor.
- **Acción**: Recolectar 3 URLs públicas representativas por builder, ejecutar el scraper, ajustar selectores, añadir fixtures a `tests/integration/scraper/`.
- **Dueño**: técnico (Samuel).

### WCM-004 — Decidir hosting de R2 vs uploads locales por defecto
- **Tipo**: feature / **Fase**: 9 / **Prioridad**: P2
- **Estado**: OPEN
- **Contexto**: Cloudflare R2 está fijado en el stack para assets, pero algunos clientes querrán que los assets vivan solo dentro de su WP destino. Necesitamos flag por proyecto.
- **Acción**: Añadir `projects.asset_storage` (`r2` | `wp_local`) y rama en el asset-optimizer.

### WCM-005 — Confirmar lista ClickUp destino para tareas residuales
- **Tipo**: chore / **Fase**: 10 / **Prioridad**: P2
- **Estado**: OPEN
- **Contexto**: El prompt fija lista "Microtareas" `900102088242` por defecto, pero deberíamos confirmar si para migraciones grandes preferimos lista propia por proyecto.
- **Acción**: Consultar con Nacho. Documentar en `docs/decisiones.md`.

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
- **Dueño**: técnico (Samuel / Álvaro).

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
- **Dueño**: humano (Álvaro).

---

### WCM-012 — Habilitar Places API (New) cuando sea posible
- **Tipo**: chore / **Fase**: 9 (post) / **Prioridad**: P3
- **Estado**: OPEN
- **Contexto**: La API key del proyecto solo tiene habilitada Places API legacy (ADR-024). La New tiene mejor field-mask y precio. Migrar cuando billing/google permita.
- **Acción**: Habilitar Places API (New) en Google Cloud Console y reescribir `packages/scraper-core/src/wcm_scraper_core/directories/google_places.py` para usar `places.googleapis.com/v1/places:searchText`. Tests con MockTransport siguen valiendo.
- **Dueño**: técnico.

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
