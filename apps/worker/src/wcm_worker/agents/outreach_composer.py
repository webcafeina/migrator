"""OutreachComposerAgent — genera borradores de email LSSI-CE compliant.

NUNCA envía. Persiste un `OutreachSequence` con `status=DRAFT_PENDING_REVIEW`
y un `OutreachSend` por paso de la secuencia con `status=QUEUED`. El operador
revisa en el dashboard antes de marcar la secuencia como READY (envío real
queda fuera del MVP — Fase 10 con Resend).

Reglas LSSI-CE / RGPD aplicadas (skill gdpr-compliance):
- B2B explícito: usamos `legal_ground=6.1.f` (interés legítimo art. 6.1.f
  RGPD + art. 21.2 LSSI-CE para servicios profesionales).
- Bloque legal obligatorio al pie con razón social + CIF + dirección.
- Enlace de opt-out funcional con un solo clic (token JWT firmado).
- Tono no agresivo, una sola CTA, sin manipulación.
- Idioma ES por defecto.

Validación previa al render:
- El lead DEBE tener al menos un email.
- El lead NO debe estar en `opt_out_log` (cualquiera de sus emails).
- Si está, lanzamos OutreachComposerError("opted_out") — el orchestrator
  marca el lead como OPTED_OUT y no se crea la secuencia.

v0.14.0 — pipeline HTML:
- Si el OutreachTemplate tiene `body_html_template`, el composer lo
  usa directamente; si no, envuelve el texto plano de `body_template`
  en HTML básico vía `wrap_plain_as_html`.
- El composer carga el layout maestro de `email_layouts` (singleton
  con fallback hardcoded), lo combina con el contenido + CTA + logo +
  legal, inlinea CSS con premailer y persiste el HTML final en
  `OutreachSend.body_html_rendered` además del text plano en
  `body_rendered` (snapshot dual para que la UI muestre exactamente
  lo enviado aunque la plantilla cambie después).
- La validación legal sigue operando sobre TEXT derivado (`html_to_text`
  del HTML final), no sobre el markup — desacopla validación de
  formato. Si la legal_block o el opt_out_url están en el HTML como
  href, `html_to_text` los extrae y la validación los detecta.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from sqlalchemy import select

from wcm_db.models.audit import AuditLog
from wcm_db.models.leads import Lead, OptOutLog
from wcm_db.models.outreach import OutreachSend, OutreachSequence
from wcm_types.enums import (
    AuditAction,
    LeadStatus,
    OutreachChannel,
    OutreachSendStatus,
    OutreachSequenceStatus,
)
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.errors import OutreachComposerError
from wcm_worker.integrations.email_layout import load_layout, render_full_email
from wcm_worker.integrations.html_email import html_to_text, is_html, wrap_plain_as_html

log = logging.getLogger("wcm.worker.outreach_composer")

#: Versión del validador legal. Incrementar cuando cambien las reglas
#: LSSI-CE/RGPD aplicadas para poder auditar qué secuencias usaron qué
#: política. Se persiste en `outreach_sequences.legal_validator_version`.
LEGAL_VALIDATOR_VERSION = "v1.0"


@dataclass(frozen=True)
class _RenderedTemplate:
    """Resultado del render de una plantilla: triple subject + body
    texto + body HTML inyectado en el layout maestro, listo para
    persistirse en OutreachSend.

    `body_text` puede ser idéntico al original (si la plantilla era
    texto) o derivado del HTML (si la plantilla era HTML). Siempre se
    persiste en `body_rendered` y se usa para la validación legal.
    `body_html` siempre lleva CSS inlined.
    """

    subject: str
    body_text: str
    body_html: str
    cta_label: str | None
    cta_url: str | None


#: Secuencia por defecto: intro + 1 followup tras 5 días laborables. La
#: cadencia exacta la decide el operador en el dashboard.
_DEFAULT_SEQUENCE_STEPS = (
    {"template": "wix_intro_es", "delay_days": 0},
    {"template": "followup_es", "delay_days": 5},
)


class OutreachComposerAgent(BaseAgent):
    name = "outreach-composer"
    phase_name = "compose_outreach"

    def __init__(
        self,
        *,
        templates_dir: str | Path | None = None,
        sender_name: str = "Equipo Webcafeína",
    ) -> None:
        self.sender_name = sender_name
        if templates_dir is None:
            templates_dir = _default_templates_dir()
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(disabled_extensions=("j2",), default=False),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.lead_id is None:
            raise OutreachComposerError("OutreachComposerAgent requiere lead_id en ctx")

        lead = ctx.session.get(Lead, ctx.lead_id)
        if lead is None:
            raise OutreachComposerError(f"Lead {ctx.lead_id} no encontrado")

        if not lead.emails:
            raise OutreachComposerError(f"Lead {lead.id} sin email — no se puede componer outreach")

        opted = self._check_opted_out(ctx, lead.emails)
        if opted:
            lead.status = LeadStatus.OPTED_OUT
            ctx.session.add(
                AuditLog(
                    actor="outreach-composer",
                    action=AuditAction.OPT_OUT,
                    entity_type="lead",
                    entity_id=str(lead.id),
                    legal_ground="6.1.f",
                    payload={"reason": "previously_opted_out", "email": opted},
                )
            )
            ctx.session.flush()
            raise OutreachComposerError(
                f"Lead {lead.id} previamente opted-out ({opted}). No se compone."
            )

        settings = ctx.extra.get("company") or _read_company_from_env()
        opt_out_token = ctx.extra.get("opt_out_token")
        if not opt_out_token:
            raise OutreachComposerError(
                "OutreachComposerAgent requiere ctx.extra['opt_out_token'] "
                "(emitido por apps.api.security.issue_opt_out_token)"
            )
        opt_out_url = f"{settings['opt_out_url_base']}?token={opt_out_token}"
        # v0.14.0 — el layout maestro embebe el logo si EMAIL_LOGO_URL
        # está configurado (en env). Sin él, layout cae a "webcafeína"
        # texto estilado (edge case #4 del plan).
        logo_url = os.environ.get("EMAIL_LOGO_URL", "").strip() or None

        steps_cfg = ctx.extra.get("steps") or list(_DEFAULT_SEQUENCE_STEPS)
        template_ctx = _build_template_context(
            lead=lead,
            settings=settings,
            opt_out_url=opt_out_url,
            sender_name=self.sender_name,
            logo_url=logo_url,
        )

        rendered_steps: list[dict[str, Any]] = []
        for step in steps_cfg:
            tpl_name = step["template"]
            rt = self._render_template(tpl_name, template_ctx, ctx)
            rendered_steps.append(
                {
                    "template": tpl_name,
                    "delay_days": step.get("delay_days", 0),
                    "subject": rt.subject,
                    # `body` mantiene compat con el shape histórico
                    # (texto plano) — la UI legacy de v0.13.x leía
                    # `step.body`. v0.14.0 añade `body_html` y el
                    # contact-sequence-panel lo prefiere si existe.
                    "body": rt.body_text,
                    "body_html": rt.body_html,
                    "cta_label": rt.cta_label,
                    "cta_url": rt.cta_url,
                }
            )

        validation_errors = _validate_legal_compliance(rendered_steps, settings)
        if validation_errors:
            raise OutreachComposerError(f"Validación legal falló: {'; '.join(validation_errors)}")

        seq = OutreachSequence(
            lead_id=lead.id,
            template_name=steps_cfg[0]["template"],
            name=f"Outreach inicial · {lead.business_name or lead.url}",
            channel=OutreachChannel.EMAIL,
            steps_json=rendered_steps,
            status=OutreachSequenceStatus.DRAFT_PENDING_REVIEW,
            legal_validation_passed=True,
            legal_validator_version=LEGAL_VALIDATOR_VERSION,
        )
        ctx.session.add(seq)
        ctx.session.flush()  # para obtener seq.id

        for idx, rendered in enumerate(rendered_steps):
            ctx.session.add(
                OutreachSend(
                    sequence_id=seq.id,
                    lead_id=lead.id,
                    step_index=idx,
                    channel=OutreachChannel.EMAIL,
                    subject=rendered["subject"],
                    body_rendered=rendered["body"],
                    # v0.14.0 — snapshot HTML del envío (NULL ok si el
                    # render HTML falló y degradamos a text-only).
                    body_html_rendered=rendered.get("body_html") or None,
                    status=OutreachSendStatus.QUEUED,
                )
            )

        lead.status = LeadStatus.OUTREACH_PREPARED

        ctx.session.add(
            AuditLog(
                actor="outreach-composer",
                action=AuditAction.CREATE,
                entity_type="outreach_sequence",
                entity_id=str(seq.id),
                legal_ground="6.1.f",
                payload={
                    "lead_id": lead.id,
                    "steps": len(rendered_steps),
                    "validator_version": LEGAL_VALIDATOR_VERSION,
                },
            )
        )

        ctx.session.flush()
        return AgentResult(
            summary=f"Sequence {seq.id} · {len(rendered_steps)} steps · lead {lead.id}",
            outputs={
                "sequence_id": seq.id,
                "steps": [
                    {"step_index": i, "subject": s["subject"], "delay_days": s["delay_days"]}
                    for i, s in enumerate(rendered_steps)
                ],
                "validator_version": LEGAL_VALIDATOR_VERSION,
            },
        )

    # ---------- helpers ----------

    def _render_template(
        self,
        tpl_name: str,
        template_ctx: dict[str, Any],
        agent_ctx: AgentContext,
    ) -> _RenderedTemplate:
        """Resuelve subject + body texto + body HTML de una plantilla.

        Estrategia de resolución (igual que pre-v0.14.0, ampliada con HTML):
        1. Busca en BD por `outreach_templates.name`. Si encuentra:
           - subject = render(`subject_template`)
           - body_text = render(`body_template`)
           - body_html_content = render(`body_html_template`) si existe;
             si NULL/vacío → `wrap_plain_as_html(body_text)`.
           - CTA = (`cta_label`, `cta_url`) tal cual.
        2. Si BD no devuelve plantilla → fallback a fichero `.j2` en
           disco (`<name>.subject.j2` + `<name>.body.j2`). Sin HTML
           dedicado: HTML se deriva del text con `wrap_plain_as_html`.

        En ambos casos se carga el LAYOUT MAESTRO (singleton
        `email_layouts` con fallback hardcoded), se compone el HTML
        final (layout + slot + CTA + logo + legal), se aplica premailer
        para inlinear CSS, y se retorna `_RenderedTemplate`.

        El text final (`body_text`) es lo que se persiste como
        `body_rendered` y lo que se valida legalmente — para texto
        plano original es el render directo; para HTML es el resultado
        de `html_to_text` sobre el HTML final con layout (así el
        validador "ve" footer legal + opt-out que viven en el layout,
        no en el slot).
        """
        # Lazy import — mismo patrón que pre-v0.14.0 para no acoplar
        # el composer al modelo si la BD aún no tiene la tabla.
        from wcm_db.models.outreach import OutreachTemplate

        stmt = select(OutreachTemplate).where(OutreachTemplate.name == tpl_name)
        try:
            row = agent_ctx.session.execute(stmt).scalar_one_or_none()
        except Exception:  # noqa: BLE001 — tabla no existe / BD inalcanzable
            row = None

        cta_label: str | None = None
        cta_url: str | None = None

        if isinstance(row, OutreachTemplate):
            subject = self._render_from_string(
                row.subject_template, template_ctx, f"{tpl_name}.subject (BD)"
            )
            body_text = self._render_from_string(
                row.body_template, template_ctx, f"{tpl_name}.body (BD)"
            )
            if row.body_html_template:
                body_html_content = self._render_from_string(
                    row.body_html_template, template_ctx, f"{tpl_name}.body_html (BD)"
                )
            else:
                body_html_content = wrap_plain_as_html(body_text)
            cta_label = row.cta_label
            cta_url = row.cta_url
        else:
            # Fallback a fichero .j2 (sin HTML dedicado).
            subject = self._render(f"{tpl_name}.subject.j2", template_ctx)
            body_text = self._render(f"{tpl_name}.body.j2", template_ctx)
            body_html_content = wrap_plain_as_html(body_text)

        # Si el body_html viene como texto plano sin tags conocidos
        # (caso defensivo) lo envolvemos también, para que el slot
        # `{{ content | safe }}` reciba siempre HTML válido.
        if not is_html(body_html_content):
            body_html_content = wrap_plain_as_html(body_html_content)

        # Inyectar contenido en el layout maestro + premailer.
        try:
            layout = load_layout(agent_ctx.session)
            full_html = render_full_email(
                layout,
                content_html=body_html_content,
                subject=subject,
                cta_label=cta_label,
                cta_url=cta_url,
                logo_url=template_ctx.get("logo_url"),
                template_ctx=template_ctx,
            )
        except Exception as e:  # noqa: BLE001 — layout/premailer falló
            log.warning(
                "outreach_html_render_failed_text_only",
                extra={"template": tpl_name, "error": str(e)},
            )
            return _RenderedTemplate(
                subject=subject,
                body_text=body_text,
                body_html="",  # señal de degradación al sender
                cta_label=cta_label,
                cta_url=cta_url,
            )

        # text final = del HTML para que validate_step encuentre lo
        # que aporta el layout (legal_block, opt-out URL, etc.).
        # Si por algún motivo el text derivado pierde info, mantenemos
        # el body_text original como mínimo de seguridad.
        derived_text = html_to_text(full_html) or body_text

        return _RenderedTemplate(
            subject=subject,
            body_text=derived_text,
            body_html=full_html,
            cta_label=cta_label,
            cta_url=cta_url,
        )

    def _render(self, template_name: str, ctx: dict[str, Any]) -> str:
        try:
            return self._env.get_template(template_name).render(**ctx).strip()
        except Exception as e:
            raise OutreachComposerError(f"Error renderizando template {template_name}: {e}") from e

    def _render_from_string(self, source: str, ctx: dict[str, Any], label: str) -> str:
        try:
            return self._env.from_string(source).render(**ctx).strip()
        except Exception as e:
            raise OutreachComposerError(f"Error renderizando template {label}: {e}") from e

    def _check_opted_out(self, ctx: AgentContext, emails: list[str]) -> str | None:
        """Devuelve el primer email del lead que esté ya en opt_out_log."""
        stmt = select(OptOutLog.email).where(OptOutLog.email.in_(emails))
        row = ctx.session.execute(stmt).first()
        return row[0] if row else None


def _default_templates_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "templates" / "outreach"


def _read_company_from_env() -> dict[str, str]:
    """Construye el dict con datos legales desde variables de entorno.

    Mantenemos un dict en lugar de una clase Pydantic porque el worker se
    despliega independiente del API y no compartimos `ApiSettings`.
    """
    legal_name = os.environ.get("COMPANY_LEGAL_NAME", "Webcafeína S.L.")
    cif = os.environ.get("COMPANY_CIF", "").strip()
    address = os.environ.get("COMPANY_ADDRESS", "").strip()
    contact = os.environ.get("COMPANY_CONTACT_EMAIL", "info@webcafeina.com")
    privacy = os.environ.get(
        "COMPANY_PRIVACY_POLICY_URL",
        "https://webcafeina.com/politica-de-privacidad",
    )
    opt_out_base = os.environ.get(
        "OUTREACH_OPT_OUT_URL_BASE", "https://migrator.webcafeina.com/opt-out"
    )

    missing = [n for n, v in [("COMPANY_CIF", cif), ("COMPANY_ADDRESS", address)] if not v]
    if missing:
        raise OutreachComposerError(
            f"Datos legales obligatorios ausentes en env: {missing}. "
            "Sin estos datos no se puede generar outreach LSSI-CE compliant."
        )

    return {
        "legal_name": legal_name,
        "cif": cif,
        "address": address,
        "contact_email": contact,
        "privacy_url": privacy,
        "opt_out_url_base": opt_out_base,
    }


def _build_template_context(
    *,
    lead: Lead,
    settings: dict[str, Any],
    opt_out_url: str,
    sender_name: str,
    logo_url: str | None = None,
) -> dict[str, Any]:
    builder_label = _builder_to_label(lead.builder_detected)
    legal_block = (
        f"{settings['legal_name']} · CIF {settings['cif']} · "
        f"{settings['address']} · {settings['contact_email']}. "
        f"Tratamiento de datos al amparo del art. 6.1.f RGPD (interés "
        f"legítimo, contacto B2B). Más info en {settings['privacy_url']}."
    )
    # Vars para el cuerpo de la plantilla (legacy + nuevo) y para el
    # layout maestro v0.14.0. Mantengo los nombres legacy
    # (`company_name`, `legal_block`) y añado los aliases explícitos
    # que el layout HTML usa (`company_legal_name`, `company_cif`,
    # `company_address`, `privacy_policy_url`, `logo_url`).
    return {
        "business_name": lead.business_name or "",
        "website_url": lead.url,
        "builder_label": builder_label,
        "sender_name": sender_name,
        # Legacy (plantillas .j2 / texto).
        "company_name": settings["legal_name"],
        "company_city": _city_from_address(settings["address"]),
        "company_contact_email": settings["contact_email"],
        "legal_block": legal_block,
        "opt_out_url": opt_out_url,
        "previous_subject": "vuestra web",
        # v0.14.0 — layout maestro HTML.
        "company_legal_name": settings["legal_name"],
        "company_cif": settings["cif"],
        "company_address": settings["address"],
        "privacy_policy_url": settings["privacy_url"],
        "logo_url": logo_url or "",
    }


def _builder_to_label(builder: Any) -> str:
    if builder is None:
        return "vuestra plataforma actual"
    value = builder.value if hasattr(builder, "value") else str(builder)
    return {
        "wix": "Wix",
        "hostinger_ai": "Hostinger AI Builder",
        "webflow": "Webflow",
        "squarespace": "Squarespace",
        "shopify": "Shopify",
        "wordpress": "WordPress",
    }.get(value.lower(), "vuestra plataforma actual")


def _city_from_address(address: str) -> str:
    """Extracción laxa: última coma → último token. Para `Santa Cristina,
    s/n – Edificio Embarcadero, 10195 Cáceres` devuelve "Cáceres".
    """
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if not parts:
        return ""
    tokens = parts[-1].split()
    return tokens[-1] if tokens else parts[-1]


def _validate_legal_compliance(steps: list[dict[str, Any]], settings: dict[str, Any]) -> list[str]:
    """Reglas mínimas que TODO outreach debe pasar antes de persistirse."""
    errors: list[str] = []
    base_opt_out = settings["opt_out_url_base"].split("?")[0]
    for idx, step in enumerate(steps):
        body = step.get("body", "")
        if settings["legal_name"] not in body:
            errors.append(f"step {idx}: falta razón social")
        if settings["cif"] and settings["cif"] not in body:
            errors.append(f"step {idx}: falta CIF")
        if settings["address"] and settings["address"] not in body:
            errors.append(f"step {idx}: falta dirección postal")
        if base_opt_out not in body:
            errors.append(f"step {idx}: falta enlace de opt-out funcional")
        if not step.get("subject"):
            errors.append(f"step {idx}: subject vacío")
    return errors


# ---------- API pública (consumida desde el API HTTP) ----------


def validate_outreach_steps(steps: list[dict[str, Any]], settings: dict[str, Any]) -> list[str]:
    """Helper público para revalidar steps tras edición manual desde la
    UI. Mismas reglas que la validación que el composer corre al generar
    el draft inicial — single source of truth para qué cuenta como
    "LSSI-CE compliant"."""
    return _validate_legal_compliance(steps, settings)


def load_company_legal_settings() -> dict[str, str]:
    """Helper público equivalente a `_read_company_from_env`. Lanza
    `OutreachComposerError` si faltan CIF/ADDRESS — mismo
    comportamiento que el composer al arrancar."""
    return _read_company_from_env()
