"""Tests de los endpoints v0.27.0 B4 — Brief refinement.

POST /brief/suggest-refinements + GET /brief/refinements + POST
/brief/apply-refinement. Mockea enqueue + sesión.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from wcm_api.routers.projects import _apply_refinement_to_brief


def _make_project_with_brief(
    project_id: int = 1,
    brief: dict | None = None,
    proposals: list | None = None,
    proposals_meta: dict | None = None,
):
    p = MagicMock()
    p.id = project_id
    p.client_name = "Demo S.L."
    p.source_url = "https://demo.example/"
    p.brief_json = brief or {
        "business": {"name": "Demo"},
        "pages": [{
            "slug": "home",
            "sections": [
                {"type": "hero", "design_method": "ai", "headline": "Hi"},
                {"type": "cta", "design_method": "templates",
                 "cta_text": "Contact", "cta_url": "/c"},
            ],
        }],
    }
    base_meta = proposals_meta or {
        "generated_at": "2026-05-22T20:00:00+00:00",
        "model": "gpt-5.5",
        "cost_usd": 0.012,
        "tokens_in": 1500,
        "tokens_out": 400,
    }
    p.brief_refinement_proposals_json = (
        {**base_meta, "proposals": proposals} if proposals is not None else None
    )
    return p


# ---------- helper _apply_refinement_to_brief ----------


def test_apply_copy_actualiza_headline() -> None:
    brief = {
        "pages": [{"slug": "home", "sections": [{"type": "hero", "headline": "Hi"}]}]
    }
    proposal = {
        "category": "copy", "page_slug": "home", "section_index": 0,
        "before": {"key": "headline", "value": "Hi"},
        "after": {"key": "headline", "value": "Bienvenidos"},
    }
    out = _apply_refinement_to_brief(brief, proposal)
    assert out["pages"][0]["sections"][0]["headline"] == "Bienvenidos"


def test_apply_cta_actualiza_cta_text_y_url() -> None:
    brief = {
        "pages": [{"slug": "home", "sections": [
            {"type": "cta", "cta_text": "Old", "cta_url": "/old"}
        ]}]
    }
    proposal = {
        "category": "cta", "page_slug": "home", "section_index": 0,
        "before": {"cta_text": "Old", "cta_url": "/old"},
        "after": {"cta_text": "Pedir presupuesto", "cta_url": "/contact"},
    }
    out = _apply_refinement_to_brief(brief, proposal)
    sec = out["pages"][0]["sections"][0]
    assert sec["cta_text"] == "Pedir presupuesto"
    assert sec["cta_url"] == "/contact"


def test_apply_design_method_cambia_method() -> None:
    brief = {
        "pages": [{"slug": "home", "sections": [
            {"type": "hero", "design_method": "templates"}
        ]}]
    }
    proposal = {
        "category": "design_method", "page_slug": "home", "section_index": 0,
        "before": {"design_method": "templates"},
        "after": {"design_method": "ai"},
    }
    out = _apply_refinement_to_brief(brief, proposal)
    assert out["pages"][0]["sections"][0]["design_method"] == "ai"


def test_apply_reorder_permuta_secciones() -> None:
    brief = {"pages": [{"slug": "home", "sections": [
        {"type": "hero"}, {"type": "cta"}, {"type": "features"},
    ]}]}
    proposal = {
        "category": "reorder", "page_slug": "home", "section_index": 0,
        "before": {"new_order": [0, 1, 2]},
        "after": {"new_order": [2, 0, 1]},
    }
    out = _apply_refinement_to_brief(brief, proposal)
    types = [s["type"] for s in out["pages"][0]["sections"]]
    assert types == ["features", "hero", "cta"]


def test_apply_reorder_lista_invalida_lanza_valueerror() -> None:
    brief = {"pages": [{"slug": "home", "sections": [{"type": "hero"}, {"type": "cta"}]}]}
    proposal = {
        "category": "reorder", "page_slug": "home", "section_index": 0,
        "before": {}, "after": {"new_order": [1]},  # len mismatch
    }
    with pytest.raises(ValueError, match="reorder new_order"):
        _apply_refinement_to_brief(brief, proposal)


def test_apply_section_index_fuera_de_rango_lanza_valueerror() -> None:
    brief = {"pages": [{"slug": "home", "sections": [{"type": "hero"}]}]}
    proposal = {
        "category": "copy", "page_slug": "home", "section_index": 5,
        "before": {}, "after": {"key": "headline", "value": "x"},
    }
    with pytest.raises(ValueError, match="section_index"):
        _apply_refinement_to_brief(brief, proposal)


def test_apply_page_slug_no_existente_lanza_valueerror() -> None:
    brief = {"pages": [{"slug": "home", "sections": []}]}
    proposal = {
        "category": "copy", "page_slug": "missing", "section_index": 0,
        "before": {}, "after": {"key": "headline", "value": "x"},
    }
    with pytest.raises(ValueError, match="page_slug.*missing"):
        _apply_refinement_to_brief(brief, proposal)


# ---------- POST /brief/suggest-refinements ----------


@pytest.mark.asyncio
async def test_suggest_refinements_encola(client, operator_token, fake_session) -> None:
    project = _make_project_with_brief()
    fake_session.get.return_value = project
    with patch(
        "wcm_api.routers.projects.enqueue_brief_suggest_refinements",
        return_value="task-uuid",
    ) as mock_enqueue:
        response = await client.post(
            "/api/v1/projects/1/brief/suggest-refinements",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
    assert response.status_code == 202
    body = response.json()
    assert body["task_id"] == "task-uuid"
    assert body["status"] == "queued"
    mock_enqueue.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_suggest_refinements_409_sin_brief(client, operator_token, fake_session) -> None:
    project = _make_project_with_brief(brief={"business": {}, "pages": []})
    fake_session.get.return_value = project
    response = await client.post(
        "/api/v1/projects/1/brief/suggest-refinements",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 409


# ---------- GET /brief/refinements ----------


@pytest.mark.asyncio
async def test_get_refinements_devuelve_batch(client, operator_token, fake_session) -> None:
    project = _make_project_with_brief(
        proposals=[
            {
                "id": "p1", "category": "copy", "page_slug": "home",
                "section_index": 0,
                "before": {"key": "headline", "value": "Hi"},
                "after": {"key": "headline", "value": "Bienvenidos"},
                "rationale": "Más impactante.",
                "impact_estimate": "high",
                "applied_at": None,
            },
        ],
    )
    fake_session.get.return_value = project
    response = await client.get(
        "/api/v1/projects/1/brief/refinements",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "gpt-5.5"
    assert body["cost_usd"] == 0.012
    assert len(body["proposals"]) == 1
    assert body["proposals"][0]["id"] == "p1"


@pytest.mark.asyncio
async def test_get_refinements_vacio_si_sin_propuestas(client, operator_token, fake_session) -> None:
    project = _make_project_with_brief(proposals=None)
    fake_session.get.return_value = project
    response = await client.get(
        "/api/v1/projects/1/brief/refinements",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["proposals"] == []
    assert body["cost_usd"] == 0.0


# ---------- POST /brief/apply-refinement ----------


@pytest.mark.asyncio
async def test_apply_refinement_sin_regenerate(client, operator_token, fake_session) -> None:
    """Aplica al Brief, NO encola regenerate, marca applied_at."""
    proposal = {
        "id": "p1", "category": "copy", "page_slug": "home",
        "section_index": 0,
        "before": {"key": "headline", "value": "Hi"},
        "after": {"key": "headline", "value": "Bienvenidos"},
        "rationale": "x", "impact_estimate": "high",
        "applied_at": None,
    }
    project = _make_project_with_brief(proposals=[proposal])
    fake_session.get.return_value = project

    with patch(
        "wcm_api.routers.projects.enqueue_preview_regenerate_page",
        return_value="never-called",
    ) as mock_enqueue:
        response = await client.post(
            "/api/v1/projects/1/brief/apply-refinement",
            headers={"Authorization": f"Bearer {operator_token}"},
            json={"proposal_id": "p1", "regenerate": False},
        )
    assert response.status_code == 202
    body = response.json()
    assert body["already_applied"] is False
    assert body["regenerated"] is False
    assert body["regenerate_task_id"] is None
    mock_enqueue.assert_not_called()
    # Brief actualizado.
    assert project.brief_json["pages"][0]["sections"][0]["headline"] == "Bienvenidos"
    # applied_at seteado.
    assert proposal["applied_at"] is not None


@pytest.mark.asyncio
async def test_apply_refinement_con_regenerate(client, operator_token, fake_session) -> None:
    proposal = {
        "id": "p2", "category": "cta", "page_slug": "home",
        "section_index": 1,
        "before": {"cta_text": "Contact"},
        "after": {"cta_text": "Pedir presupuesto"},
        "rationale": "x", "impact_estimate": "medium",
        "applied_at": None,
    }
    project = _make_project_with_brief(proposals=[proposal])
    fake_session.get.return_value = project

    with patch(
        "wcm_api.routers.projects.enqueue_preview_regenerate_page",
        return_value="regen-task-id",
    ) as mock_enqueue:
        response = await client.post(
            "/api/v1/projects/1/brief/apply-refinement",
            headers={"Authorization": f"Bearer {operator_token}"},
            json={"proposal_id": "p2", "regenerate": True},
        )
    assert response.status_code == 202
    body = response.json()
    assert body["regenerated"] is True
    assert body["regenerate_task_id"] == "regen-task-id"
    mock_enqueue.assert_called_once_with(1, "home")
    assert project.brief_json["pages"][0]["sections"][1]["cta_text"] == "Pedir presupuesto"


@pytest.mark.asyncio
async def test_apply_refinement_404_si_proposal_no_existe(
    client, operator_token, fake_session,
) -> None:
    project = _make_project_with_brief(proposals=[])
    fake_session.get.return_value = project
    response = await client.post(
        "/api/v1/projects/1/brief/apply-refinement",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={"proposal_id": "nope", "regenerate": False},
    )
    assert response.status_code == 404
