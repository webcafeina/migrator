"""Tests del pipeline HTML del OutreachComposerAgent (v0.14.0).

Cubrimos:
- Plantilla con `body_html_template` → composer produce HTML con
  layout maestro + slot inyectado + CTA pintado.
- Plantilla sin `body_html_template` → composer wrappea body_template
  texto en `<p>` y mete en el layout.
- Validación legal opera sobre text derivado del HTML (no sobre el
  HTML directo), y reconoce el opt_out_url aunque viva en el `<a href>`.
- Render del layout falla → composer degrada a text-only sin romper
  el envío (body_html_rendered queda vacío en el send).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from wcm_types.enums import BuilderType, LeadStatus, OutreachSequenceStatus
from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.outreach_composer import OutreachComposerAgent

_COMPANY = {
    "legal_name": "Webcafeína S.L.",
    "cif": "B10463990",
    "address": "Santa Cristina, s/n – Edificio Embarcadero, 10195 Cáceres",
    "contact_email": "info@webcafeina.com",
    "privacy_url": "https://webcafeina.com/politica-privacidad/",
    "opt_out_url_base": "https://migrator.webcafeina.com/opt-out",
}


def _lead_mock() -> MagicMock:
    lead = MagicMock()
    lead.id = 1
    lead.url = "https://barpepe.es"
    lead.business_name = "Bar Pepe"
    lead.emails = ["hola@barpepe.es"]
    lead.builder_detected = BuilderType.WIX
    lead.status = LeadStatus.ENRICHED
    return lead


def _template_mock(
    *,
    name: str = "wix_intro_es",
    body_html_template: str | None = None,
    cta_label: str | None = None,
    cta_url: str | None = None,
) -> Any:
    """Devuelve un objeto que `isinstance(row, OutreachTemplate)` SÍ
    acepta (porque es una instancia real del modelo)."""
    from wcm_db.models.outreach import OutreachTemplate

    tpl = OutreachTemplate(
        name=name,
        subject_template="Hola {{ business_name }}",
        body_template=("Hola {{ business_name }}.\n\n{{ legal_block }}\n\nBaja: {{ opt_out_url }}"),
        language="es",
        body_html_template=body_html_template,
        cta_label=cta_label,
        cta_url=cta_url,
    )
    return tpl


def _setup_session_with_template(fake_session, lead, template, *, steps: int = 1):
    """fake_session.get(Lead, id) → lead.

    Configura las llamadas a `session.execute` en el orden en que
    ocurren dentro del composer:
      1. opt_out_log (verificación previa, 1 vez en total).
      2. Por cada step: SELECT OutreachTemplate WHERE name=...
      3. Por cada step: SELECT EmailLayout WHERE id=1 (load_layout).

    Devolvemos `None` para EmailLayout para que `load_layout` caiga al
    fallback hardcoded — el render del layout funciona igual y no
    depende de la migración 0005 estando aplicada.
    """
    fake_session.get.return_value = lead

    optout_res = MagicMock()
    optout_res.first.return_value = None

    tpl_res = MagicMock()
    tpl_res.scalar_one_or_none.return_value = template

    layout_res = MagicMock()
    layout_res.scalar_one_or_none.return_value = None  # → fallback

    execute_sequence: list[Any] = [optout_res]
    for _ in range(steps):
        execute_sequence.extend([tpl_res, layout_res])
    fake_session.execute.side_effect = execute_sequence


def _ctx(fake_session) -> AgentContext:
    return AgentContext(
        session=fake_session,
        lead_id=1,
        extra={
            "company": _COMPANY,
            "opt_out_token": "tk-html",
            "steps": [{"template": "wix_intro_es", "delay_days": 0}],
        },
    )


def test_composer_uses_body_html_template_when_present(fake_session) -> None:
    """Si la plantilla BD tiene body_html_template, el HTML del send
    debe contener su contenido (no la versión texto envuelta)."""
    lead = _lead_mock()
    tpl = _template_mock(
        body_html_template="<p><strong>Hola</strong> {{ business_name }}</p>",
        cta_label="Hablamos",
        cta_url="https://cal.com/wcm",
    )
    _setup_session_with_template(fake_session, lead, tpl)

    added: list[Any] = []
    fake_session.add.side_effect = lambda obj: added.append(obj)

    # asignar id al sequence al flush (mismo patrón que el test legacy).
    def _add_with_id(obj):
        if type(obj).__name__ == "OutreachSequence" and obj.id is None:
            obj.id = 77
        added.append(obj)

    fake_session.add.side_effect = _add_with_id

    OutreachComposerAgent().run(_ctx(fake_session))

    sends = [o for o in added if type(o).__name__ == "OutreachSend"]
    assert len(sends) == 1
    s = sends[0]
    # El HTML final tiene el strong + el cta + el footer legal del layout.
    assert s.body_html_rendered is not None
    assert "<strong>" in s.body_html_rendered
    assert "Bar Pepe" in s.body_html_rendered
    assert "Hablamos" in s.body_html_rendered
    assert "cal.com/wcm" in s.body_html_rendered
    # El body_rendered (text) trae el opt-out URL gracias al `texto (url)`
    # de html_to_text.
    assert "opt-out" in s.body_rendered


def test_composer_wraps_plain_template_when_no_html(fake_session) -> None:
    """Plantilla sin body_html_template → composer envuelve body texto
    en <p> y lo mete en el layout. CTA queda fuera (NULL ambos campos)."""
    lead = _lead_mock()
    tpl = _template_mock(body_html_template=None, cta_label=None, cta_url=None)
    _setup_session_with_template(fake_session, lead, tpl)

    added: list[Any] = []

    def _add(obj):
        if type(obj).__name__ == "OutreachSequence" and obj.id is None:
            obj.id = 88
        added.append(obj)

    fake_session.add.side_effect = _add

    OutreachComposerAgent().run(_ctx(fake_session))

    sends = [o for o in added if type(o).__name__ == "OutreachSend"]
    s = sends[0]
    assert s.body_html_rendered is not None
    # Texto wrapeado en <p>.
    assert "<p>" in s.body_html_rendered
    # Bar Pepe del template renderizado.
    assert "Bar Pepe" in s.body_html_rendered
    # Sin CTA (no debe pintarse el anchor del botón). La REGLA CSS
    # `.wcm-cta {...}` puede seguir en el `<style>` (es estática), lo
    # que NO debería existir es un `<a ... class="wcm-cta">` real.
    assert 'class="wcm-cta"' not in s.body_html_rendered


def test_composer_persists_text_with_optout_for_validation(fake_session) -> None:
    """El body_rendered (text) debe contener el opt_out_url base para que
    la re-validación legal del editor de pasos funcione."""
    lead = _lead_mock()
    tpl = _template_mock(
        body_html_template="<p>Hola {{ business_name }}</p>",
    )
    _setup_session_with_template(fake_session, lead, tpl)

    added: list[Any] = []

    def _add(obj):
        if type(obj).__name__ == "OutreachSequence" and obj.id is None:
            obj.id = 99
        added.append(obj)

    fake_session.add.side_effect = _add

    OutreachComposerAgent().run(_ctx(fake_session))

    seqs = [o for o in added if type(o).__name__ == "OutreachSequence"]
    assert seqs[0].legal_validation_passed is True
    assert seqs[0].status == OutreachSequenceStatus.DRAFT_PENDING_REVIEW

    sends = [o for o in added if type(o).__name__ == "OutreachSend"]
    # El text derivado contiene el host del opt_out_url_base (que es
    # `migrator.webcafeina.com/opt-out`).
    assert "migrator.webcafeina.com/opt-out" in sends[0].body_rendered


def test_composer_includes_cta_in_steps_json(fake_session) -> None:
    """El steps_json debe incluir cta_label/cta_url para que la UI
    los muestre en el editor sin volver a consultar la plantilla."""
    lead = _lead_mock()
    tpl = _template_mock(
        body_html_template="<p>Hola</p>",
        cta_label="Reservar",
        cta_url="https://cal.com/x",
    )
    _setup_session_with_template(fake_session, lead, tpl)

    added: list[Any] = []

    def _add(obj):
        if type(obj).__name__ == "OutreachSequence" and obj.id is None:
            obj.id = 100
        added.append(obj)

    fake_session.add.side_effect = _add

    OutreachComposerAgent().run(_ctx(fake_session))

    seqs = [o for o in added if type(o).__name__ == "OutreachSequence"]
    step0 = seqs[0].steps_json[0]
    assert step0["cta_label"] == "Reservar"
    assert step0["cta_url"] == "https://cal.com/x"
    assert "body_html" in step0


def test_composer_degrades_gracefully_when_layout_render_fails(fake_session, monkeypatch) -> None:
    """Si el render del layout falla (vars undefined, premailer caído),
    el send se persiste solo con text — `body_html_rendered` queda
    vacío. Validación legal sigue pasando porque opera sobre el text
    plano original de la plantilla."""
    lead = _lead_mock()
    tpl = _template_mock(body_html_template="<p>Hola {{ business_name }}</p>")
    _setup_session_with_template(fake_session, lead, tpl)

    # Forzamos fallo del render_full_email para reproducir el caso.
    def _boom(*args, **kwargs):
        raise RuntimeError("layout roto")

    monkeypatch.setattr("wcm_worker.agents.outreach_composer.render_full_email", _boom)

    added: list[Any] = []

    def _add(obj):
        if type(obj).__name__ == "OutreachSequence" and obj.id is None:
            obj.id = 200
        added.append(obj)

    fake_session.add.side_effect = _add

    OutreachComposerAgent().run(_ctx(fake_session))

    sends = [o for o in added if type(o).__name__ == "OutreachSend"]
    # body_html_rendered NULL (degradación) — el sender enviará solo
    # text/plain (compat). El operador puede arreglar y re-componer.
    assert sends[0].body_html_rendered is None
    # body_rendered conserva el texto original con legal_block + opt-out
    # (el composer renderizó body_template texto antes del fallo HTML).
    assert "migrator.webcafeina.com/opt-out" in sends[0].body_rendered
