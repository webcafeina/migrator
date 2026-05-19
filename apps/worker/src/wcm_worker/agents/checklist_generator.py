"""ChecklistGeneratorAgent — entregable PDF + MD del proyecto (v0.16.0).

Flujo:
1. Carga `Project` + todas las `ResidualTask` agrupadas por categoría.
2. Renderiza markdown con plantilla Jinja2 (paleta Webcafeína).
3. Convierte MD → HTML → PDF con WeasyPrint.
4. Sube ambos (PDF + MD) a R2 si configurado, o `file://` local fallback.
5. Persiste URLs en `projects.checklist_md_url` + `projects.checklist_pdf_url`.

Categorías canónicas en orden de gravedad:
- `blocking_go_live`: NO se puede entregar sin resolverlo.
- `client_config`: configuración del cliente pendiente.
- `visual_content`: copy, imágenes, branding por revisar.
- `post_go_live`: mejoras opcionales tras lanzamiento.
- `other`: catch-all.

Resiliencia:
- WeasyPrint no disponible → solo se genera el MD + warning. El
  proyecto sigue, el operador descarga MD vía endpoint.
- R2 no configurado → paths `file://...` locales (utilidad limitada
  para el dashboard pero funcionales para el CLI).
- Sin residual tasks → checklist mínimo "Sin tareas pendientes".
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from sqlalchemy import select

from wcm_db.models.projects import Project
from wcm_db.models.residual_tasks import ResidualTask
from wcm_types.enums import ResidualCategory, ResidualStatus
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import ChecklistGeneratorError
from wcm_worker.integrations.pdf_generator import (
    render_markdown_to_html,
    render_pdf,
    weasyprint_available,
)
from wcm_worker.integrations.r2 import R2Client

log = logging.getLogger("wcm.worker.checklist_generator")

#: Orden y labels de categorías en el checklist.
_CATEGORY_ORDER: list[tuple[ResidualCategory, str, str | None]] = [
    (
        ResidualCategory.BLOCKING_GO_LIVE,
        "Bloqueantes para go-live",
        "Estas tareas DEBEN resolverse antes de entregar el sitio al cliente.",
    ),
    (
        ResidualCategory.CLIENT_CONFIG,
        "Configuración del cliente",
        "Acciones que requieren credenciales o decisiones del cliente.",
    ),
    (
        ResidualCategory.VISUAL_CONTENT,
        "Contenido visual",
        "Copy, imágenes y branding que requieren revisión humana.",
    ),
    (
        ResidualCategory.POST_GO_LIVE,
        "Post go-live (opcionales)",
        "Mejoras y optimizaciones recomendadas tras el lanzamiento.",
    ),
    (
        ResidualCategory.OTHER,
        "Otras",
        None,
    ),
]

#: Labels castellano de los status.
_STATUS_LABELS: dict[ResidualStatus, str] = {
    ResidualStatus.OPEN: "Pendiente",
    ResidualStatus.IN_PROGRESS: "En curso",
    ResidualStatus.BLOCKED: "Bloqueada",
    ResidualStatus.SKIPPED: "Saltada",
    ResidualStatus.DONE: "Hecha",
}


class ChecklistGeneratorAgent(BaseAgent):
    name = "checklist-generator"
    phase_name = "generate_checklist"

    def __init__(
        self,
        *,
        r2: R2Client | None = None,
        templates_dir: Path | str | None = None,
    ) -> None:
        self._injected_r2 = r2
        if templates_dir is None:
            templates_dir = Path(__file__).resolve().parent.parent / "templates" / "checklist"
        self._templates_dir = Path(templates_dir)
        self._env = Environment(
            loader=FileSystemLoader(str(self._templates_dir)),
            autoescape=select_autoescape(disabled_extensions=("j2", "md")),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise ChecklistGeneratorError("ChecklistGeneratorAgent requiere project_id")

        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise ChecklistGeneratorError(f"Project {ctx.project_id} no encontrado")

        residuals = self._load_residuals(ctx, project.id)
        md_text = self._render_markdown(project, residuals)

        html_body = render_markdown_to_html(md_text)
        css = self._load_css()
        full_html = self._wrap_html(html_body)

        pdf_bytes = render_pdf(full_html, css=css)
        warnings: list[str] = []
        if not pdf_bytes and not weasyprint_available():
            warnings.append(
                "WeasyPrint no disponible — solo MD generado. "
                "Instala libs SO: `apt install libpango-1.0-0 libpangoft2-1.0-0 "
                "libcairo2 libgdk-pixbuf2.0-0` (Linux) o reinstala WeasyPrint."
            )

        r2 = self._injected_r2 or R2Client.from_env()
        md_url, pdf_url = self._upload_two(
            r2,
            project_id=project.id,
            md_bytes=md_text.encode("utf-8"),
            pdf_bytes=pdf_bytes,
        )

        project.checklist_md_url = md_url
        project.checklist_pdf_url = pdf_url
        ctx.session.flush()

        return AgentResult(
            summary=(
                f"Project {project.id}: checklist generado · "
                f"{len(residuals)} tarea(s) · "
                f"PDF={'OK' if pdf_bytes else 'SKIPPED'} · MD=OK"
            ),
            outputs={
                "residual_tasks_count": len(residuals),
                "pdf_generated": bool(pdf_bytes),
                "md_url": md_url,
                "pdf_url": pdf_url,
            },
            warnings=warnings,
        )

    # ---------- helpers ----------

    def _load_residuals(self, ctx: AgentContext, project_id: int) -> list[ResidualTask]:
        stmt = (
            select(ResidualTask)
            .where(ResidualTask.project_id == project_id)
            .order_by(ResidualTask.category.asc(), ResidualTask.id.asc())
        )
        return list(ctx.session.execute(stmt).scalars().all())

    def _render_markdown(self, project: Project, residuals: list[ResidualTask]) -> str:
        by_category: dict[ResidualCategory, list[ResidualTask]] = {}
        for r in residuals:
            by_category.setdefault(r.category, []).append(r)

        categories = []
        for cat, label, description in _CATEGORY_ORDER:
            tasks = by_category.get(cat, [])
            categories.append(
                {
                    "label": label,
                    "description": description,
                    "tasks": [self._task_to_dict(t) for t in tasks],
                }
            )

        total_open = sum(1 for r in residuals if r.status == ResidualStatus.OPEN)
        total_in_progress = sum(1 for r in residuals if r.status == ResidualStatus.IN_PROGRESS)
        total_blocked = sum(1 for r in residuals if r.status == ResidualStatus.BLOCKED)
        total_skipped = sum(1 for r in residuals if r.status == ResidualStatus.SKIPPED)
        total_done = sum(1 for r in residuals if r.status == ResidualStatus.DONE)
        total_pending = total_open + total_in_progress + total_blocked

        estimated_total = sum(
            (r.estimated_minutes or 0)
            for r in residuals
            if r.status in (ResidualStatus.OPEN, ResidualStatus.IN_PROGRESS)
        )

        ctx_data = {
            "client_name": project.client_name,
            "project_id": project.id,
            "source_url": project.source_url,
            "target_domain": project.target_domain,
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            "project_status": project.status.value,
            "total_open": total_open,
            "total_in_progress": total_in_progress,
            "total_blocked": total_blocked,
            "total_skipped": total_skipped,
            "total_done": total_done,
            "total_pending": total_pending,
            "estimated_minutes_total": estimated_total,
            "estimated_hours_human": _format_hours(estimated_total),
            "categories": categories,
            "company_contact_email": os.environ.get("COMPANY_CONTACT_EMAIL", "info@webcafeina.com"),
            "company_address": os.environ.get("COMPANY_ADDRESS", "Cáceres, España"),
        }

        template = self._env.get_template("checklist.md.j2")
        return template.render(**ctx_data).strip() + "\n"

    def _task_to_dict(self, task: ResidualTask) -> dict:
        return {
            "title": task.title,
            "description": task.description,
            "status_label": _STATUS_LABELS.get(task.status, task.status.value),
            "estimated_minutes": task.estimated_minutes,
            "generated_by": task.generated_by,
            "assignee_hint": task.assignee_hint,
            "clickup_task_id": task.clickup_task_id,
        }

    def _load_css(self) -> str:
        css_path = self._templates_dir / "checklist.css"
        if not css_path.exists():
            return ""
        return css_path.read_text(encoding="utf-8")

    def _wrap_html(self, body: str) -> str:
        return (
            "<!doctype html>\n"
            '<html lang="es">\n'
            '<head><meta charset="utf-8"><title>Checklist Webcafeína</title></head>\n'
            "<body>\n"
            f"{body}\n"
            "</body></html>\n"
        )

    def _upload_two(
        self,
        r2: R2Client | None,
        *,
        project_id: int,
        md_bytes: bytes,
        pdf_bytes: bytes,
    ) -> tuple[str | None, str | None]:
        base_key = f"projects/{project_id}/checklist"
        if r2 is None:
            log.warning("checklist_r2_not_configured", extra={"project_id": project_id})
            return _local_fallback(base_key, md_bytes, pdf_bytes)

        md_url: str | None = None
        pdf_url: str | None = None
        try:
            md_url = r2.put_bytes(
                f"{base_key}/checklist.md",
                md_bytes,
                content_type="text/markdown; charset=utf-8",
                metadata={"project_id": str(project_id), "kind": "checklist-md"},
            )
        except Exception as e:  # noqa: BLE001
            log.warning(
                "checklist_md_upload_failed",
                extra={"project_id": project_id, "error": str(e)},
            )

        if pdf_bytes:
            try:
                pdf_url = r2.put_bytes(
                    f"{base_key}/checklist.pdf",
                    pdf_bytes,
                    content_type="application/pdf",
                    metadata={
                        "project_id": str(project_id),
                        "kind": "checklist-pdf",
                    },
                )
            except Exception as e:  # noqa: BLE001
                log.warning(
                    "checklist_pdf_upload_failed",
                    extra={"project_id": project_id, "error": str(e)},
                )
        return md_url, pdf_url


def _format_hours(minutes: int) -> str:
    """120 → '2 h'. 90 → '1 h 30 min'. <60 → 'X min'."""
    if minutes < 60:
        return f"{minutes} min"
    h, m = divmod(minutes, 60)
    if m == 0:
        return f"{h} h"
    return f"{h} h {m} min"


def _local_fallback(
    base_key: str, md_bytes: bytes, pdf_bytes: bytes
) -> tuple[str | None, str | None]:
    """Escribe MD + PDF a /tmp/wcm-checklist/... y devuelve `file://` URLs."""
    import tempfile

    root = os.path.join(tempfile.gettempdir(), "wcm-checklist", base_key)
    os.makedirs(root, exist_ok=True)
    md_path = os.path.join(root, "checklist.md")
    pdf_path = os.path.join(root, "checklist.pdf")
    with open(md_path, "wb") as f:
        f.write(md_bytes)
    md_url = f"file://{md_path}"
    pdf_url: str | None = None
    if pdf_bytes:
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        pdf_url = f"file://{pdf_path}"
    return md_url, pdf_url
