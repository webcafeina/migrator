"""Tests de `PATCH /api/v1/outreach/sequences/{id}/steps` (v0.12.0).

Edición de pasos por el operador antes de aprobar. Re-corre validación
legal y actualiza `legal_validation_passed`.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wcm_types.enums import OutreachChannel, OutreachSequenceStatus


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seq_mock(
    *,
    seq_id: int = 1,
    status: OutreachSequenceStatus = OutreachSequenceStatus.DRAFT_PENDING_REVIEW,
    legal_passed: bool = True,
) -> MagicMock:
    seq = MagicMock()
    seq.id = seq_id
    seq.lead_id = 5
    seq.name = "Outreach inicial · Test"
    seq.template_name = "wix_intro_es"
    seq.channel = OutreachChannel.EMAIL
    seq.steps_json = [
        {"step_index": 0, "subject": "old", "body": "old body", "delay_days_from_previous": 0},
    ]
    seq.status = status
    seq.legal_validation_passed = legal_passed
    seq.legal_validator_version = "v1.0"
    from datetime import UTC, datetime
    now = datetime.now(UTC)
    seq.created_at = now
    seq.updated_at = now
    return seq


_VALID_BODY = (
    "Hola, soy el equipo de Webcafeína S.L. · CIF B10463990 · "
    "Santa Cristina s/n. Opt-out: https://example.com/opt-out"
)
_VALID_PAYLOAD = {
    "steps": [
        {
            "step_index": 0,
            "subject": "Nuevo asunto",
            "body": _VALID_BODY,
            "delay_days_from_previous": 0,
        },
    ],
}


@pytest.mark.asyncio
async def test_edit_steps_requires_operator(
    client, viewer_token
) -> None:
    resp = await client.patch(
        "/api/v1/outreach/sequences/1/steps",
        headers=_auth(viewer_token),
        json=_VALID_PAYLOAD,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_edit_steps_404_when_sequence_missing(
    client, fake_session, operator_token
) -> None:
    fake_session.get = AsyncMock(return_value=None)
    resp = await client.patch(
        "/api/v1/outreach/sequences/999/steps",
        headers=_auth(operator_token),
        json=_VALID_PAYLOAD,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_edit_steps_409_when_status_not_editable(
    client, fake_session, operator_token
) -> None:
    """SENT/READY/COMPLETED no se pueden editar — cancelar + recomponer."""
    fake_session.get = AsyncMock(
        return_value=_seq_mock(status=OutreachSequenceStatus.READY)
    )
    resp = await client.patch(
        "/api/v1/outreach/sequences/1/steps",
        headers=_auth(operator_token),
        json=_VALID_PAYLOAD,
    )
    assert resp.status_code == 409
    assert "estado" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_edit_steps_pasa_validacion_legal_actualiza_seq(
    client, fake_session, operator_token
) -> None:
    """Cuando los nuevos pasos pasan validación, legal_validation_passed
    queda True y la sequence actualiza steps_json."""
    seq = _seq_mock()
    fake_session.get = AsyncMock(return_value=seq)

    with (
        patch(
            "wcm_worker.agents.outreach_composer.load_company_legal_settings"
        ) as mock_settings,
        patch(
            "wcm_worker.agents.outreach_composer.validate_outreach_steps"
        ) as mock_validate,
    ):
        mock_settings.return_value = {
            "legal_name": "Webcafeína S.L.",
            "cif": "B10463990",
            "address": "Santa Cristina s/n",
            "opt_out_url_base": "https://example.com/opt-out",
            "contact_email": "info@webcafeina.com",
            "privacy_url": "https://example.com/privacy",
        }
        mock_validate.return_value = []  # validación OK

        resp = await client.patch(
            "/api/v1/outreach/sequences/1/steps",
            headers=_auth(operator_token),
            json=_VALID_PAYLOAD,
        )

    assert resp.status_code == 200
    assert seq.legal_validation_passed is True
    assert seq.steps_json[0]["subject"] == "Nuevo asunto"


@pytest.mark.asyncio
async def test_edit_steps_falla_validacion_marca_legal_passed_false(
    client, fake_session, operator_token
) -> None:
    """Si la edición rompe validación, legal_validation_passed=False y
    el endpoint sigue devolviendo 200 (es el frontend quien deshabilita
    el botón Aprobar). El AuditLog refleja los errores."""
    seq = _seq_mock()
    fake_session.get = AsyncMock(return_value=seq)

    with (
        patch(
            "wcm_worker.agents.outreach_composer.load_company_legal_settings"
        ) as mock_settings,
        patch(
            "wcm_worker.agents.outreach_composer.validate_outreach_steps"
        ) as mock_validate,
    ):
        mock_settings.return_value = {
            "legal_name": "Webcafeína S.L.",
            "cif": "B10463990",
            "address": "Santa Cristina s/n",
            "opt_out_url_base": "https://example.com/opt-out",
            "contact_email": "info@webcafeina.com",
            "privacy_url": "https://example.com/privacy",
        }
        mock_validate.return_value = [
            "step 0: falta razón social",
            "step 0: falta enlace de opt-out funcional",
        ]

        resp = await client.patch(
            "/api/v1/outreach/sequences/1/steps",
            headers=_auth(operator_token),
            json={
                "steps": [
                    {
                        "step_index": 0,
                        "subject": "Bonito",
                        "body": "Pero falta footer legal",
                        "delay_days_from_previous": 0,
                    },
                ],
            },
        )

    assert resp.status_code == 200
    assert seq.legal_validation_passed is False
    # AuditLog escrito con los errores
    audit_logs = [
        call.args[0] for call in fake_session.add.call_args_list
        if getattr(call.args[0], "entity_type", None) == "outreach_sequence"
    ]
    assert len(audit_logs) == 1
    audit = audit_logs[0]
    assert audit.payload["legal_validation_passed"] is False
    assert "step 0: falta razón social" in audit.payload["legal_errors"]


@pytest.mark.asyncio
async def test_edit_steps_empty_list_422(client, operator_token) -> None:
    """steps debe tener min_length=1."""
    resp = await client.patch(
        "/api/v1/outreach/sequences/1/steps",
        headers=_auth(operator_token),
        json={"steps": []},
    )
    assert resp.status_code == 422
