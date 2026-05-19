"""FormsRebuilderAgent — recrea formularios origen en Gravity Forms (v0.17.0).

Flujo:
1. Verifica que el plugin Gravity Forms está activo
   (GET /wp-json/gf/v2/forms con auth).
   - Si NO está: ResidualTask 'instalar Gravity Forms' + fase SKIPPED.
2. Parsea `html_raw` de cada `scraped_pages` con BeautifulSoup, extrae
   `<form>` y sus campos (`input`/`textarea`/`select`).
3. Mapea HTML5 input types → tipos de campo Gravity Forms.
4. Para cada formulario detectado:
   - Si ya existe por título → log y skip (idempotente).
   - Si no: POST /wp-json/gf/v2/forms con la definición.
   - Añade notificación email al admin del proyecto
     (COMPANY_CONTACT_EMAIL o env `WP_DEFAULT_NOTIFY_EMAIL`).
5. ResidualTask informativa con el listado de forms detectados +
   acciones manuales recomendadas (cambiar copy, conectar CRM, etc).

NO migra historial de envíos. Es trivial pero ruidoso e improbable
que sea útil al cliente; queda como residual manual si lo necesita.

Mapping HTML5 → Gravity Forms (referencia oficial GF):
- text/email/url/tel/number → text/email/website/phone/number
- textarea → textarea
- select → select (con choices del DOM)
- radio/checkbox → radio/checkbox
- file → fileupload
- date → date
- hidden → hidden
- submit/button → no se mapea (GF añade su propio submit)

Resiliencia:
- Sin Gravity Forms instalado → fase SKIPPED + residual claro.
- Sin forms detectados en el origen → fase salta limpia.
- Form individual falla al crear → warning, sigue con el siguiente.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

from bs4 import BeautifulSoup
from sqlalchemy import select

from wcm_db.models.projects import Project
from wcm_db.models.residual_tasks import ResidualTask
from wcm_db.models.scraped_pages import ScrapedPage
from wcm_types.enums import ResidualCategory, ResidualStatus, ScrapeStatus
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import FormsRebuilderError
from wcm_wp_client import WpClientConfig, WpRestClient
from wcm_wp_client.errors import WpRestError

log = logging.getLogger("wcm.worker.forms_rebuilder")


#: Mapping HTML5 input type → Gravity Forms field type.
#: GF types: https://docs.gravityforms.com/category/developers/php-api/field-objects/
_FIELD_TYPE_MAP: dict[str, str] = {
    "text": "text",
    "email": "email",
    "url": "website",
    "tel": "phone",
    "phone": "phone",
    "number": "number",
    "password": "password",
    "date": "date",
    "datetime-local": "date",
    "time": "time",
    "file": "fileupload",
    "hidden": "hidden",
    "search": "text",
    "color": "text",
}


class FormsRebuilderAgent(BaseAgent):
    name = "forms-rebuilder"
    phase_name = "rebuild_forms"

    def __init__(self, *, wp_config: WpClientConfig | None = None) -> None:
        self._injected_config = wp_config

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.project_id is None:
            raise FormsRebuilderError("FormsRebuilderAgent requiere project_id")

        project = ctx.session.get(Project, ctx.project_id)
        if project is None:
            raise FormsRebuilderError(f"Project {ctx.project_id} no encontrado")

        try:
            wp_config = self._injected_config or WpClientConfig.from_env()
        except ValueError as e:
            raise FormsRebuilderError(
                f"Config WP destino incompleta en .env: {e}"
            ) from e

        # 1. Detectar forms en origen ANTES de tocar el destino — barato.
        pages = list(
            ctx.session.execute(
                select(ScrapedPage).where(
                    ScrapedPage.project_id == project.id,
                    ScrapedPage.status == ScrapeStatus.SUCCESS,
                )
            ).scalars().all()
        )
        detected = _detect_forms(pages)

        if not detected:
            return AgentResult(
                summary=f"Project {project.id}: 0 formularios detectados en origen.",
                outputs={"gravity_forms_available": None, "forms_created": 0},
            )

        notify_email = (
            os.environ.get("WP_DEFAULT_NOTIFY_EMAIL")
            or os.environ.get("COMPANY_CONTACT_EMAIL")
            or "info@webcafeina.com"
        )

        return asyncio.run(
            self._build(wp_config, project, detected, notify_email, ctx)
        )

    async def _build(
        self,
        wp_config: WpClientConfig,
        project: Project,
        detected: list[DetectedForm],
        notify_email: str,
        ctx: AgentContext,
    ) -> AgentResult:
        warnings: list[str] = []

        async with WpRestClient(wp_config) as rest:
            if not await _gravity_forms_available(rest):
                created = _add_residual(
                    ctx,
                    project.id,
                    title="Instalar y activar Gravity Forms en el WP destino",
                    description=(
                        f"Se detectaron {len(detected)} formulario(s) en el "
                        "origen, pero el plugin Gravity Forms no responde "
                        "en `/wp-json/gf/v2/forms`. Pasos:\n\n"
                        "1. Subir el .zip de Gravity Forms al WP destino "
                        "(WordPress admin → Plugins → Subir).\n"
                        "2. Activar el plugin y registrar la licencia.\n"
                        "3. Re-ejecutar `forms-rebuilder` desde el dashboard."
                    ),
                    category=ResidualCategory.BLOCKING_GO_LIVE,
                    estimated_minutes=30,
                )
                ctx.session.flush()
                return AgentResult(
                    summary=(
                        f"Project {project.id}: Gravity Forms NO instalado, "
                        f"{len(detected)} forms quedan pendientes."
                    ),
                    outputs={
                        "gravity_forms_available": False,
                        "forms_detected": len(detected),
                        "forms_created": 0,
                    },
                    warnings=[
                        "Gravity Forms no detectado. Pipeline continúa; "
                        "revisa el checklist."
                    ],
                    residual_tasks_created=created,
                )

            # 2. Listar forms existentes (para evitar duplicados por título).
            existing_titles = await _list_existing_form_titles(rest)

            created_count = 0
            for form in detected:
                if form.title in existing_titles:
                    warnings.append(
                        f"Form '{form.title}' ya existe en destino — skipped"
                    )
                    continue
                try:
                    payload = _build_gf_payload(form, notify_email)
                    await rest._request("POST", "/gf/v2/forms", json=payload)
                    created_count += 1
                except Exception as e:  # noqa: BLE001
                    warnings.append(
                        f"Form '{form.title}' falló: {type(e).__name__}: {e}"
                    )
                    log.warning(
                        "gf_form_create_failed",
                        extra={
                            "project_id": project.id,
                            "title": form.title,
                            "error": str(e),
                        },
                    )

            # 3. Residual informativa con resumen y acciones recomendadas.
            review_residual = _add_residual(
                ctx,
                project.id,
                title=f"Revisar {created_count} formulario(s) Gravity Forms",
                description=(
                    "Los formularios se han creado en modo `inactive`. "
                    "Acciones pendientes:\n\n"
                    f"- Revisar labels y placeholders (notificación email "
                    f"actual: `{notify_email}`).\n"
                    "- Activar cada form desde Formularios → tu form → "
                    "Configuración → Estado.\n"
                    "- Insertarlos en las páginas finales con el shortcode "
                    "`[gravityform id=N]` o el bloque Bricks.\n"
                    "- Si hay integraciones (Mailchimp, CRM, Slack), "
                    "configurarlas manualmente — no se migran."
                ),
                category=ResidualCategory.CLIENT_CONFIG,
                estimated_minutes=15 + created_count * 5,
            )

            ctx.session.flush()

            return AgentResult(
                summary=(
                    f"Project {project.id}: {created_count}/"
                    f"{len(detected)} formularios creados en Gravity Forms."
                ),
                outputs={
                    "gravity_forms_available": True,
                    "forms_detected": len(detected),
                    "forms_created": created_count,
                },
                warnings=warnings,
                residual_tasks_created=review_residual,
            )


# ---------- detección + mapping ----------


class DetectedForm:
    """Form parseado del origen. Estructura mínima para construir GF payload."""

    __slots__ = ("title", "source_url", "fields")

    def __init__(self, title: str, source_url: str, fields: list[dict[str, Any]]) -> None:
        self.title = title
        self.source_url = source_url
        self.fields = fields


def _detect_forms(pages: list[ScrapedPage]) -> list[DetectedForm]:
    """Parsea html_raw de cada page, extrae `<form>` y campos.

    Dedupe por título normalizado (varias copias del mismo form en
    distintas páginas → solo una).
    """
    seen: dict[str, DetectedForm] = {}
    for page in pages:
        if not page.html_raw:
            continue
        try:
            soup = BeautifulSoup(page.html_raw, "lxml")
        except Exception:
            soup = BeautifulSoup(page.html_raw, "html.parser")

        for form_tag in soup.find_all("form"):
            fields = _extract_fields(form_tag)
            if not fields:
                continue
            title = _guess_form_title(form_tag, page) or f"Formulario en {page.slug or page.url}"
            key = _normalize_title(title)
            if key in seen:
                continue
            seen[key] = DetectedForm(
                title=title[:120],
                source_url=page.url,
                fields=fields,
            )
    return list(seen.values())


def _extract_fields(form_tag: Any) -> list[dict[str, Any]]:
    """De un `<form>` BS4 saca campos canonicalizados."""
    fields: list[dict[str, Any]] = []
    field_id = 1

    for el in form_tag.find_all(["input", "textarea", "select"]):
        tag = el.name
        if tag == "input":
            input_type = (el.get("type") or "text").lower()
            if input_type in ("submit", "button", "image", "reset"):
                continue
        name = el.get("name") or ""
        if not name:
            continue
        label = _find_label(el, form_tag) or el.get("placeholder") or name

        if tag == "textarea":
            gf_type = "textarea"
        elif tag == "select":
            gf_type = "select"
        else:
            gf_type = _FIELD_TYPE_MAP.get(input_type, "text")

        f: dict[str, Any] = {
            "id": field_id,
            "type": gf_type,
            "label": label[:255],
            "isRequired": el.get("required") is not None,
        }
        if tag == "select":
            f["choices"] = [
                {"text": (o.get_text() or o.get("value") or "").strip(), "value": o.get("value") or o.get_text() or ""}
                for o in el.find_all("option")
                if (o.get("value") or o.get_text())
            ]
        if (tag == "input" and (el.get("type") or "").lower() in ("radio", "checkbox")):
            # Radio/checkbox grupos los mete WP como uno solo más adelante; al
            # encontrarlos sueltos los mapeamos como text para no romper.
            f["type"] = el.get("type")
            f["choices"] = [
                {"text": label, "value": el.get("value") or label}
            ]
        fields.append(f)
        field_id += 1

    return fields


def _find_label(el: Any, form_tag: Any) -> str | None:
    """Busca el <label for=id> o el label envolvente."""
    el_id = el.get("id")
    if el_id:
        lbl = form_tag.find("label", attrs={"for": el_id})
        if lbl:
            return lbl.get_text(strip=True)
    # Label envolvente
    parent = el.parent
    if parent and parent.name == "label":
        return parent.get_text(strip=True)
    return None


def _guess_form_title(form_tag: Any, page: ScrapedPage) -> str | None:
    """Heurística: aria-label, name, id, o <legend> dentro."""
    for attr in ("aria-label", "name", "id"):
        val = form_tag.get(attr)
        if val:
            return val.replace("-", " ").replace("_", " ").strip().title()
    legend = form_tag.find("legend")
    if legend:
        return legend.get_text(strip=True)
    h = form_tag.find(["h1", "h2", "h3"])
    if h:
        return h.get_text(strip=True)
    return None


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.lower().strip())


def _build_gf_payload(form: DetectedForm, notify_email: str) -> dict[str, Any]:
    """Construye el payload JSON que espera `POST /gf/v2/forms`."""
    return {
        "title": form.title,
        "description": f"Migrado desde {form.source_url}",
        "labelPlacement": "top_label",
        "descriptionPlacement": "below",
        "button": {"type": "text", "text": "Enviar"},
        "fields": form.fields,
        "is_active": "0",  # creado inactivo para revisión manual
        "notifications": {
            "1": {
                "id": "1",
                "name": "Notificación admin (migrado)",
                "event": "form_submission",
                "to": notify_email,
                "subject": f"Nuevo envío: {form.title}",
                "message": "{all_fields}",
                "fromName": "Web",
                "from": "{admin_email}",
                "isActive": True,
            }
        },
    }


# ---------- helpers GF API ----------


async def _gravity_forms_available(rest: WpRestClient) -> bool:
    """GET /gf/v2/forms — 200 si plugin activo, 404 si no."""
    try:
        await rest._request("GET", "/gf/v2/forms")
        return True
    except WpRestError as e:
        if getattr(e, "status_code", None) in (401, 403, 404):
            return False
        raise


async def _list_existing_form_titles(rest: WpRestClient) -> set[str]:
    """Devuelve set de títulos normalizados de los forms ya existentes."""
    try:
        r = await rest._request("GET", "/gf/v2/forms")
        body = r.json()
    except Exception:  # noqa: BLE001
        return set()
    titles: set[str] = set()
    # GF puede devolver dict {id: form_data} o list dependiendo de la versión.
    if isinstance(body, dict):
        for v in body.values():
            if isinstance(v, dict) and v.get("title"):
                titles.add(v["title"])
    elif isinstance(body, list):
        for item in body:
            if isinstance(item, dict) and item.get("title"):
                titles.add(item["title"])
    return titles


def _add_residual(
    ctx: AgentContext,
    project_id: int,
    *,
    title: str,
    description: str,
    category: ResidualCategory,
    estimated_minutes: int,
) -> int:
    ctx.session.add(
        ResidualTask(
            project_id=project_id,
            title=title,
            description=description,
            category=category,
            status=ResidualStatus.OPEN,
            estimated_minutes=estimated_minutes,
            generated_by="forms-rebuilder",
        )
    )
    return 1
