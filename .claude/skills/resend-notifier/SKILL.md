---
name: resend-notifier
description: Envío de notificaciones por email vía Resend a operadores Webcafeína. Plantillas HTML con paleta de marca para eventos del sistema (proyecto completado, error crítico, presupuesto agotado, etc.). NO se usa para enviar outreach a leads (eso es revisión humana siempre).
---

# Skill — Resend Notifier

## Propósito

Notificar al equipo Webcafeína de eventos relevantes del sistema. Tono operacional, no marketing.

## Contrato

```python
class ResendNotifier:
    def __init__(self, api_key: str, from_email: str = "migrator@webcafeina.com"):
        ...

    def notify(
        self,
        event: NotificationEvent,
        recipients: list[str] | None = None,  # default: NOTIFY_OPERATIONS
    ) -> ResendMessageId:
        """Renderiza plantilla y envía."""
```

## Tipos de evento soportados

Todas las notificaciones van al equipo Webcafeína (env `RESEND_NOTIFY_OPERATIONS`, default `info@webcafeina.com`). Sin escalación a personas concretas.

| Event | Recipients | Plantilla |
|---|---|---|
| `project.completed` | NOTIFY_OPERATIONS | `project_completed.html` |
| `project.qa_failed` | NOTIFY_OPERATIONS | `qa_failed.html` |
| `project.blocked_human_input` | NOTIFY_OPERATIONS | `human_input_needed.html` |
| `error.critical` | NOTIFY_OPERATIONS | `error_critical.html` |
| `prospect.campaign_completed` | NOTIFY_OPERATIONS | `campaign_completed.html` |
| `prospect.budget_exceeded` | NOTIFY_OPERATIONS | `budget_exceeded.html` |
| `system.deploy_started` | NOTIFY_OPERATIONS | `deploy_started.html` |
| `system.deploy_failed` | NOTIFY_OPERATIONS | `deploy_failed.html` |

## Plantillas HTML

Viven en `apps/api/templates/emails/`. Estructura:

```
emails/
├── _base.html              # layout maestro
├── _components/
│   ├── header.html         # logo Webcafeína + nombre app
│   ├── footer.html         # copyright + opt-out interno
│   ├── button.html         # CTA estilizado
│   └── data-table.html
└── project_completed.html
    qa_failed.html
    ...
```

`_base.html` aplica paleta:

```css
body  { background: #171009; color: #F2E8D2; font-family: 'Inter', sans-serif; }
.card { background: #2B1A0E; padding: 24px; border-radius: 8px; }
.accent { color: #B1F100; }
.btn   { background: #B1F100; color: #171009; padding: 12px 24px; ... }
.detail-brown { color: #5A3519; }
```

## Datos por evento

`NotificationEvent` es un union:

```python
@dataclass
class ProjectCompletedEvent:
    project_id: int
    client_name: str
    target_domain: str
    visual_diff_avg: float
    residual_tasks_count: int
    dashboard_url: str
    checklist_pdf_url: str

@dataclass
class ErrorCriticalEvent:
    project_id: int | None
    component: str
    message: str
    stack_trace_excerpt: str
    sentry_event_id: str
    dashboard_url: str

# etc.
```

## Características

- **Idempotencia**: evento con `dedup_key` (e.g. `project-42-completed`) no se envía dos veces en una ventana de 1h (cache Redis).
- **Plantillas en español de España**, sin emojis.
- **Sin marketing**: subjects descriptivos, no clickbait. Ejemplo: `"[Migrator] Proyecto 42 completado — ejemplo.com"`.
- **Reply-To**: `info@webcafeina.com` para que las respuestas lleguen al inbox principal.

## Errores tipados

- `ResendNotifierError` (raíz)
- `ResendApiError`
- `TemplateRenderError`
- `RecipientUnverifiedError` — Resend exige verificación de dominios sender; gestionar setup en infra

## NO es para outreach a leads

- El outreach pasa por `outreach-composer` con revisión humana.
- Este skill envía SOLO a direcciones internas Webcafeína (`@webcafeina.com`).
- Sanity check: si recipient no termina en `@webcafeina.com`, ERROR (excepto whitelist explícita).

## Tests

- Mock Resend API
- Test idempotencia (mismo dedup_key, segunda vez no envía)
- Test recipient whitelist (intentar enviar a externo → error)

## Dependencias

- `resend` SDK Python oficial
- `jinja2` para plantillas
- Credenciales: `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `RESEND_NOTIFY_OPERATIONS`
