"""Tests de delete_project_r2_assets (limpieza R2 al borrar proyecto)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from wcm_api.services.project_cleanup import delete_project_r2_assets


def test_skipped_si_r2_no_configurado() -> None:
    """R2Client.from_env() devuelve None → skipped sin error."""
    with patch("wcm_worker.integrations.r2.R2Client.from_env", return_value=None):
        result = delete_project_r2_assets(42)
    assert result == {"status": "skipped", "reason": "r2_not_configured", "deleted": 0}


def test_happy_path_borra_y_devuelve_count() -> None:
    """R2 disponible y delete_prefix devuelve N → status ok + métricas.

    W (2026-05-21) — prefix unificado a `wcm/projects/{id}/` (antes era
    `projects/{id}/` aquí pero `wcm/projects/` en asset_optimizer, lo
    que dejaba huérfanos en R2).
    """
    fake_client = MagicMock()
    fake_client.delete_prefix.return_value = 7
    with patch(
        "wcm_worker.integrations.r2.R2Client.from_env", return_value=fake_client
    ):
        result = delete_project_r2_assets(42)
    fake_client.delete_prefix.assert_called_once_with("wcm/projects/42/")
    assert result == {"status": "ok", "prefix": "wcm/projects/42/", "deleted": 7}


def test_r2_prefix_template_consistente_con_asset_optimizer() -> None:
    """W — el PROJECT_R2_PREFIX_TEMPLATE debe coincidir con la base que
    construye `asset_optimizer._r2_key`. Si alguno divergiera, los
    proyectos dejarían objetos huérfanos en R2 al borrarse."""
    from wcm_api.services.project_cleanup import PROJECT_R2_PREFIX_TEMPLATE
    from wcm_worker.agents.asset_optimizer import AssetOptimizerAgent

    agent = AssetOptimizerAgent.__new__(AssetOptimizerAgent)
    key = agent._r2_key(99, "deadbeef" * 8, "image/webp")
    expected_prefix = PROJECT_R2_PREFIX_TEMPLATE.format(project_id=99)
    assert key.startswith(expected_prefix), (
        f"asset_optimizer genera '{key}' que NO empieza por '{expected_prefix}'. "
        "Si divergen, project_cleanup deja huérfanos en R2."
    )


def test_error_no_levanta_solo_loguea() -> None:
    """Si delete_prefix falla → status=error pero NO raise (delete BD sigue)."""
    from wcm_worker.integrations.r2 import R2UploadError

    fake_client = MagicMock()
    fake_client.delete_prefix.side_effect = R2UploadError("network blip")
    with patch(
        "wcm_worker.integrations.r2.R2Client.from_env", return_value=fake_client
    ):
        result = delete_project_r2_assets(42)
    assert result["status"] == "error"
    assert "network blip" in result["reason"]
    assert result["deleted"] == 0


def test_prefix_vacio_no_permitido() -> None:
    """delete_prefix con prefix vacío levanta (evita borrado masivo accidental)."""
    import pytest

    from wcm_worker.integrations.r2 import R2Client, R2UploadError

    client = R2Client(
        account_id="acc",
        access_key_id="ak",
        secret_access_key="sk",
        bucket="b",
        public_url_base=None,
        s3_client=MagicMock(),  # bypass boto3 boot
    )
    with pytest.raises(R2UploadError, match="prefix no vacío"):
        client.delete_prefix("")
