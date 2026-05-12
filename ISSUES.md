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
- **Estado**: OPEN
- **Contexto**: Para outreach LSSI-CE compliant se necesitan CIF y dirección postal completos. La política de privacidad debe estar publicada en una URL estable.
- **Acción**: Rellenar `COMPANY_CIF`, `COMPANY_ADDRESS`, `COMPANY_PRIVACY_POLICY_URL` en `.env` de producción y validar `apps/api/legal/plantilla_aviso_legal_outreach.md`.
- **Dueño**: humano (Nacho).

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

### WCM-006 — Política de retención de leads sin consentimiento
- **Tipo**: docs / **Fase**: 9 / **Prioridad**: P1
- **Estado**: OPEN
- **Contexto**: Bajo RGPD, los leads enriquecidos con datos de contacto pero sin consentimiento explícito tienen una vida útil limitada bajo interés legítimo. Definir TTL (sugerido 12 meses) y job de purga.
- **Acción**: Documentar política en `apps/api/legal/tratamiento_datos_prospeccion.md` y crear task Celery `purge_expired_leads`.

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
