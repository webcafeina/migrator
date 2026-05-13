# Política de retención de datos (leads y outreach)

**Responsable**: Webcafeína S.L.  
**Última actualización**: 2026-05-13.

| Entidad | Retención | Acción al expirar | Justificación |
|---|---|---|---|
| `leads` (status DISCOVERED, sin outreach) | 12 meses desde `created_at` | borrar (cascade limpia enrichments) | Sin tratamiento posterior, no hay base legítima para mantenerlo |
| `leads` (status OUTREACH_SENT o posterior, sin respuesta) | 24 meses desde último envío | mover a `status=DISCARDED`, borrar tras 6 meses adicionales | Permite reactivación durante 2 años; tras 30 meses sin interés mutuo, se descarta |
| `leads` (status CONVERTED) | indefinida — pasa a relación contractual | n/a — gobierno por contrato cliente | Cliente activo, no aplica esta política |
| `lead_enrichments` | cascada con `leads` | cascade DELETE | FK ON DELETE CASCADE |
| `outreach_sequences` + `outreach_sends` | cascada con `leads` | cascade DELETE | FK ON DELETE CASCADE |
| `opt_out_log` | **indefinida** | nunca borrar | Base jurídica para no recontactar (interés legítimo: evitar molestia al ya opted-out) |
| `audit_log` (acciones sobre leads) | 5 años | mover a archivo frío, no purgar | Defensa frente a reclamación ante AEPD |
| `error_log` | 90 días | purgar | Solo trazabilidad operativa |

## Implementación

- Cron diario (Celery beat) `wcm.maintenance.retention_sweep` ejecuta la purga (no implementado — WCM-FASE10-RETENTION).
- El cron usa SQL idempotente (`DELETE FROM leads WHERE created_at < now() - interval '12 months' AND status = 'DISCOVERED' AND id NOT IN (SELECT lead_id FROM outreach_sequences)`).
- Cada purga inserta un `audit_log` con `actor='retention-sweep'`, `action=DELETE`, `payload={count, criteria}`.

## Excepciones

- Si AEPD abre expediente sobre un lead concreto, se congela la retención hasta resolución (`leads.retention_hold=true`, columna pendiente — WCM-FASE10-RETENTION).
- Los exports manuales que un operador genere desde el dashboard incluyen un campo `retention_until` calculado para que el destinatario sepa cuándo caduca.

## Revisión

Política revisada anualmente y tras cada incidente (ver `procedimiento_brecha.md`).
