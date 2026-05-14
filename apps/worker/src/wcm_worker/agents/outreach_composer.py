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
"""

from __future__ import annotations

import logging
import os
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

log = logging.getLogger("wcm.worker.outreach_composer")

#: Versión del validador legal. Incrementar cuando cambien las reglas
#: LSSI-CE/RGPD aplicadas para poder auditar qué secuencias usaron qué
#: política. Se persiste en `outreach_sequences.legal_validator_version`.
LEGAL_VALIDATOR_VERSION = "v1.0"

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
        sender_name: str = "Álvaro",
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
            raise OutreachComposerError(
                f"Lead {lead.id} sin email — no se puede componer outreach"
            )

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

        steps_cfg = ctx.extra.get("steps") or list(_DEFAULT_SEQUENCE_STEPS)
        template_ctx = _build_template_context(
            lead=lead, settings=settings, opt_out_url=opt_out_url,
            sender_name=self.sender_name,
        )

        rendered_steps: list[dict[str, Any]] = []
        for step in steps_cfg:
            tpl_name = step["template"]
            subject = self._render(f"{tpl_name}.subject.j2", template_ctx)
            body = self._render(f"{tpl_name}.body.j2", template_ctx)
            rendered_steps.append({
                "template": tpl_name,
                "delay_days": step.get("delay_days", 0),
                "subject": subject,
                "body": body,
            })

        validation_errors = _validate_legal_compliance(rendered_steps, settings)
        if validation_errors:
            raise OutreachComposerError(
                f"Validación legal falló: {'; '.join(validation_errors)}"
            )

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

    def _render(self, template_name: str, ctx: dict[str, Any]) -> str:
        try:
            return self._env.get_template(template_name).render(**ctx).strip()
        except Exception as e:
            raise OutreachComposerError(
                f"Error renderizando template {template_name}: {e}"
            ) from e

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
    *, lead: Lead, settings: dict[str, Any], opt_out_url: str, sender_name: str
) -> dict[str, Any]:
    builder_label = _builder_to_label(lead.builder_detected)
    legal_block = (
        f"{settings['legal_name']} · CIF {settings['cif']} · "
        f"{settings['address']} · {settings['contact_email']}. "
        f"Tratamiento de datos al amparo del art. 6.1.f RGPD (interés "
        f"legítimo, contacto B2B). Más info en {settings['privacy_url']}."
    )
    return {
        "business_name": lead.business_name or "",
        "website_url": lead.url,
        "builder_label": builder_label,
        "sender_name": sender_name,
        "company_name": settings["legal_name"],
        "company_city": _city_from_address(settings["address"]),
        "company_contact_email": settings["contact_email"],
        "legal_block": legal_block,
        "opt_out_url": opt_out_url,
        "previous_subject": "vuestra web",
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


def _validate_legal_compliance(
    steps: list[dict[str, Any]], settings: dict[str, Any]
) -> list[str]:
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
