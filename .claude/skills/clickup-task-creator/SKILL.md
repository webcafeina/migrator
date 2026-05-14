---
name: clickup-task-creator
description: Wrapper sobre ClickUp API v2 con plantillas de tareas Webcafeína. Crea tarea padre + subtareas, asignaciones según categoría, custom fields, tags, attachments. Maneja webhook bidireccional para sync de estado.
---

# Skill — ClickUp Task Creator

## Propósito

Encapsular la creación y actualización de tareas en ClickUp con las convenciones de Webcafeína.

## Contrato

```python
class ClickUpClient:
    def __init__(self, api_token: str, team_id: str = "20483773"):
        ...

    def create_project_task(
        self,
        project: Project,
        list_id: str = "900102088242",
    ) -> ClickUpTaskId:
        """Crea la tarea padre del proyecto."""

    def create_residual_subtasks(
        self,
        parent_task_id: str,
        residual_tasks: list[ResidualTask],
    ) -> dict[ResidualTaskId, ClickUpTaskId]:
        """Crea subtarea por cada residual; asigna automáticamente."""

    def update_task_status(self, clickup_task_id: str, status: str) -> None: ...
    def attach_file(self, clickup_task_id: str, file_path: Path) -> None: ...
    def register_webhook(self, endpoint_url: str, events: list[str], secret: str) -> WebhookId: ...
    def verify_webhook_signature(self, signature: str, body: bytes, secret: str) -> bool: ...
```

## Plantilla tarea padre

```python
def render_project_task(project: Project) -> dict:
    return {
        "name": f"[Migración] {project.client_name} — {project.target_domain}",
        "description": render_project_description(project),
        "tags": [
            "migracion",
            project.builder_source or "unknown_builder",
            "pendiente-cliente" if project.has_pending_client_input() else None,
        ],
        "priority": 3,  # Normal
        "due_date": project.estimated_go_live_at,
        "custom_fields": [
            {"id": "<source_domain>", "value": project.source_url},
            {"id": "<target_domain>", "value": project.target_domain},
            {"id": "<builder>", "value": project.builder_source},
            {"id": "<visual_diff_score>", "value": project.visual_diff_avg_score},
        ],
        "custom_item_id": None,  # se usa custom_id externo:
        "custom_id": f"WCM-PROJECT-{project.id}",
    }


def render_project_description(p: Project) -> str:
    return f"""
**Proyecto de migración**

- Cliente: {p.client_name}
- Dominio origen: {p.source_url}
- Dominio destino: {p.target_domain}
- Builder origen: {p.builder_source}
- Multilang: {"sí (" + ",".join(p.langs) + ")" if p.is_multilang else "no"}
- E-commerce: {"sí" if p.has_ecommerce else "no"}

**Visual diff promedio**: {p.visual_diff_avg_score:.2f}

**Checklist completo**: [PDF]({p.checklist_pdf_url})

**Dashboard Webcafeína Migrator**: [Ver proyecto]({p.dashboard_url})
""".strip()
```

## Asignación

**Sin assignee individual** por convención del proyecto. Las subtareas se crean en ClickUp con `assignees=[]` (o con `CLICKUP_DEFAULT_ASSIGNEE` si el operador define uno común). El equipo Webcafeína decide internamente quién toma cada tarea según disponibilidad. La categoría se incluye como tag para que el equipo pueda filtrar/agrupar en ClickUp.

## Webhook

- Registrar webhook al primer sync del proyecto
- Endpoint Webcafeína Migrator: `POST /webhooks/clickup`
- Eventos: `taskStatusUpdated`, `taskCommentPosted`, `taskAssigneeUpdated`
- Validar firma HMAC SHA-256:
  ```python
  expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
  hmac.compare_digest(expected, signature)
  ```

## Rate limit

ClickUp API: 100 requests / minuto / token. Implementar rate limiter en el cliente.

## Errores tipados

- `ClickUpClientError` (raíz)
- `ClickUpAuthError`
- `ClickUpRateLimitError` (capturable, espera y reintenta)
- `ClickUpNotFoundError`
- `WebhookSignatureError`

## Tests

- Mock de ClickUp API (responses fixture)
- Test: subtareas creadas sin assignee individual (o con `CLICKUP_DEFAULT_ASSIGNEE` si está definido)
- Test webhook signature

## Dependencias

- `requests` o `httpx`
- `hmac`, `hashlib` (stdlib)
