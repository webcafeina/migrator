"""Tests de la app Celery + registro de tasks."""

from __future__ import annotations

from wcm_worker.celery_app import celery_app


def test_celery_app_registered() -> None:
    assert celery_app.main == "wcm"


def test_tasks_registered_with_expected_names() -> None:
    """Cada send_task name del API debe tener su task en el worker.

    Si esta lista cambia en el API, debe cambiar aquí también — esta es la
    razón de la asserción explícita.
    """
    # Importar tasks para forzar el registro
    import wcm_worker.tasks  # noqa: F401

    expected_names = {
        "wcm.orchestrator.run_project",
        "wcm.prospector.run_campaign",
        "wcm.fingerprinter.run",
        "wcm.clickup.sync_residuals",
    }
    registered = set(celery_app.tasks.keys())
    missing = expected_names - registered
    assert not missing, f"Tasks no registradas en el worker: {missing}"
