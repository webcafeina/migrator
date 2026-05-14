"""Tests de las tasks Celery del pipeline de prospección (WCM-026/027).

Mockeamos `session_scope`, los agents y las primitivas Celery (`chain`,
`signature`) — no usamos BD real. Se aprovecha `CELERY_TASK_ALWAYS_EAGER`
(ver conftest.py) para invocar las tasks vía `.apply()`.

Verificamos el contrato de orquestación, no la lógica de los agents.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

# ---------- helpers ----------

@contextmanager
def _fake_session_scope():
    yield MagicMock(name="session")


def _patch_session_scope(monkeypatch, module) -> None:
    monkeypatch.setattr(module, "session_scope", _fake_session_scope)


# ---------- wcm.enricher.run ----------

def test_enricher_task_invokes_agent_with_lead_id(monkeypatch) -> None:
    from wcm_worker.tasks import enricher as enricher_task

    fake_result = MagicMock(summary="ok", outputs={"score": 60})
    fake_agent_instance = MagicMock(run=MagicMock(return_value=fake_result))
    monkeypatch.setattr(enricher_task, "EnricherAgent", MagicMock(return_value=fake_agent_instance))
    _patch_session_scope(monkeypatch, enricher_task)

    out = enricher_task.run.apply(kwargs={"lead_id": 42}).get()

    assert out == {"lead_id": 42, "summary": "ok", "outputs": {"score": 60}}
    ctx_passed = fake_agent_instance.run.call_args.args[0]
    assert ctx_passed.lead_id == 42
    assert ctx_passed.extra.get("skip_embedding") is False


def test_enricher_task_propagates_skip_embedding(monkeypatch) -> None:
    from wcm_worker.tasks import enricher as enricher_task

    fake_agent_instance = MagicMock(run=MagicMock(return_value=MagicMock(summary="x", outputs={})))
    monkeypatch.setattr(enricher_task, "EnricherAgent", MagicMock(return_value=fake_agent_instance))
    _patch_session_scope(monkeypatch, enricher_task)

    enricher_task.run.apply(kwargs={"lead_id": 7, "skip_embedding": True}).get()

    ctx = fake_agent_instance.run.call_args.args[0]
    assert ctx.extra["skip_embedding"] is True


# ---------- wcm.prospector.run_campaign: chain encolado ----------

def test_prospector_task_enqueues_fingerprint_and_enrich_per_lead(monkeypatch) -> None:
    """Por cada lead creado se encolan dos tasks (fingerprint + enrich)
    independientes — sin chain — para que si fingerprint falla, enrich
    igual corra y la campaña no quede atascada.
    """
    from wcm_worker.tasks import prospector as prospector_task

    fake_agent_result = MagicMock(
        summary="ok",
        outputs={"created_lead_ids": [100, 101, 102], "discovered": 3, "created": 3},
        warnings=[],
    )
    fake_agent = MagicMock(run=MagicMock(return_value=fake_agent_result))
    monkeypatch.setattr(prospector_task, "ProspectorAgent", MagicMock(return_value=fake_agent))
    _patch_session_scope(monkeypatch, prospector_task)

    sent_tasks: list[tuple[str, dict]] = []

    def fake_send_task(name, kwargs=None, **_kw):
        sent_tasks.append((name, kwargs or {}))
        return MagicMock(id=f"task-{name}-{kwargs}")

    monkeypatch.setattr(prospector_task.celery_app, "send_task", fake_send_task)

    out = prospector_task.run_campaign.apply(
        kwargs={"sector": "restauración", "region": "Madrid", "target_count": 10}
    ).get()

    assert out["status"] == "ok"
    assert out["chained_pipelines"] == 3
    expected = [
        ("wcm.fingerprinter.run", {"lead_id": 100}),
        ("wcm.enricher.run", {"lead_id": 100}),
        ("wcm.fingerprinter.run", {"lead_id": 101}),
        ("wcm.enricher.run", {"lead_id": 101}),
        ("wcm.fingerprinter.run", {"lead_id": 102}),
        ("wcm.enricher.run", {"lead_id": 102}),
    ]
    assert sent_tasks == expected


def test_prospector_task_no_enqueue_when_zero_leads(monkeypatch) -> None:
    """Si la campaña no crea leads, no se encola nada."""
    from wcm_worker.tasks import prospector as prospector_task

    fake_agent = MagicMock(run=MagicMock(return_value=MagicMock(
        summary="empty", outputs={"created_lead_ids": []}, warnings=[],
    )))
    monkeypatch.setattr(prospector_task, "ProspectorAgent", MagicMock(return_value=fake_agent))
    _patch_session_scope(monkeypatch, prospector_task)

    fake_send = MagicMock(name="send_task")
    monkeypatch.setattr(prospector_task.celery_app, "send_task", fake_send)

    out = prospector_task.run_campaign.apply(
        kwargs={"sector": "x", "region": "y"}
    ).get()

    assert out["chained_pipelines"] == 0
    fake_send.assert_not_called()


def test_prospector_task_handles_prospector_error(monkeypatch) -> None:
    """Errores definitivos del agent → status=error, sin reintento ni enqueue."""
    from wcm_worker.errors import ProspectorError
    from wcm_worker.tasks import prospector as prospector_task

    fake_agent = MagicMock(run=MagicMock(side_effect=ProspectorError("API key inválida")))
    monkeypatch.setattr(prospector_task, "ProspectorAgent", MagicMock(return_value=fake_agent))
    _patch_session_scope(monkeypatch, prospector_task)

    fake_send = MagicMock(name="send_task")
    monkeypatch.setattr(prospector_task.celery_app, "send_task", fake_send)

    out = prospector_task.run_campaign.apply(
        kwargs={"sector": "x", "region": "y"}
    ).get()

    assert out["status"] == "error"
    assert "API key" in out["error"]
    fake_send.assert_not_called()
