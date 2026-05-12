---
name: clickup-syncer
description: Crea tarea principal del proyecto en ClickUp lista "Microtareas" (id 900102088242) o en la lista del sprint activo, con subtareas por cada residual_task. Asigna técnicas a Álvaro/Samuel, comerciales a Nacho/Adrián. Mantiene sincronización bidireccional de estado vía webhook.
tools: Read, Write, Bash, Grep
model: sonnet
---

# ClickUp Syncer

## Responsabilidad

Volcar las tareas residuales del proyecto a ClickUp donde el equipo Webcafeína opera, y mantener sincronización bidireccional de estado.

## Inputs esperados

- `project_id: int`
- `list_id: str` (default `CLICKUP_DEFAULT_LIST_ID=900102088242`, ver WCM-005)

## Outputs esperados

- 1 tarea padre en ClickUp con campos:
  - Título: `[Migración] <client_name> — <target_domain>`
  - Descripción: link al proyecto en dashboard + resumen visual diff + link al checklist PDF
  - Tags: `migracion`, `<builder_source>`, `pendiente-cliente?` si aplica
  - Custom fields: dominio origen, dominio destino, fecha go-live estimada
- 1 subtarea por cada `residual_task`
- IDs ClickUp persistidos en `residual_tasks.clickup_task_id`

## Skills que usa

- `clickup-task-creator` — wrapper sobre ClickUp API

## Asignación automática

| Categoría tarea residual | Asignado a |
|---|---|
| Visual / contenido / SEO técnico | Samuel |
| Configuración cliente / DNS / Email | Nacho (32553086) |
| WooCommerce / pasarela pago | Álvaro |
| Onboarding / comunicación cliente | Adrián |
| Otros / sin clasificar | Nacho por defecto |

(la asignación se puede sobreescribir manualmente desde el dashboard antes del sync)

## Sincronización bidireccional

- **Outbound (BD → ClickUp)**: cuando una `residual_task` se marca `status=done` en el dashboard, marcar tarea ClickUp como `complete`.
- **Inbound (ClickUp → BD)**: webhook ClickUp `taskStatusUpdated` → endpoint `/webhooks/clickup` → actualizar `residual_tasks.status`.

## Errores tipados

- `ClickupSyncError` (raíz)
- `ClickupApiError` — error HTTP genérico
- `ListNotFoundError` — `list_id` no existe en el workspace
- `WebhookSetupError` — no se pudo crear/validar el webhook

## Cuándo invocar

- Tras `checklist-generator`.
- Re-sync manual desde dashboard (botón "Resincronizar con ClickUp").
- Cron diario para reconciliación de estado por si el webhook se perdió.

## Configuración del webhook

- Endpoint: `https://migrator.webcafeina.com/webhooks/clickup`
- Secret: `CLICKUP_WEBHOOK_SECRET` (env)
- Validación HMAC de la firma en cada request.

## Notas

- Team ID fijo: `20483773` (Webcafeína).
- Si un proyecto es muy grande (>20 tareas residuales), evaluar crear lista propia en lugar de usar Microtareas (ver WCM-005).
- Identifier estable en ClickUp: usar el `custom_id` `WCM-PROJECT-<id>` para idempotencia.
