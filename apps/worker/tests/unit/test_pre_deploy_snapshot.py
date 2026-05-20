"""Tests del PreDeploySnapshotAgent (ADR-042, v0.20.0+)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wcm_worker.agents.pre_deploy_snapshot import (
    DEFAULT_SNAPSHOT_DIR,
    PreDeploySnapshotAgent,
)
from wcm_worker.errors import PreDeploySnapshotError
from wcm_wp_client import WpClientConfig
from wcm_wp_client.errors import WpCliExecutionError, WpSshConnectionError


def _wp_config() -> WpClientConfig:
    return WpClientConfig(
        site_url="https://destino.example.com",
        rest_user="user",
        rest_app_password="pass-pass-pass",
        ssh_host="destino.example.com",
        ssh_user="root",
        ssh_port=22,
        ssh_key_path="/root/.ssh/id_ed25519",
        wp_path="/var/www/html",
        wpcli_path="/usr/local/bin/wp",
        verify_ssl=True,
    )


def _ctx(project: MagicMock | None) -> MagicMock:
    ctx = MagicMock()
    ctx.project_id = 7
    ctx.extra = {}
    ctx.session = MagicMock()
    ctx.session.get.return_value = project
    return ctx


def _project_mock() -> MagicMock:
    p = MagicMock()
    p.id = 7
    p.pre_deploy_snapshot_path = None
    p.pre_deploy_snapshot_at = None
    return p


def test_requiere_project_id() -> None:
    agent = PreDeploySnapshotAgent(wp_config=_wp_config())
    ctx = _ctx(_project_mock())
    ctx.project_id = None
    with pytest.raises(PreDeploySnapshotError, match="requiere project_id"):
        agent.run(ctx)


def test_project_inexistente_levanta_error() -> None:
    agent = PreDeploySnapshotAgent(wp_config=_wp_config())
    ctx = _ctx(None)
    with pytest.raises(PreDeploySnapshotError, match="no encontrado"):
        agent.run(ctx)


def test_happy_path_persiste_path_y_timestamp() -> None:
    """Happy path: _snapshot devuelve path absoluto, run() lo persiste."""
    agent = PreDeploySnapshotAgent(wp_config=_wp_config())
    project = _project_mock()
    ctx = _ctx(project)

    expected_path = "/home/webcafeina/wcm-snapshots/project-7-20260520-120000.sql"
    with patch.object(
        PreDeploySnapshotAgent,
        "_snapshot",
        new=AsyncMock(return_value=expected_path),
    ):
        result = agent.run(ctx)

    assert project.pre_deploy_snapshot_path == expected_path
    assert isinstance(project.pre_deploy_snapshot_at, datetime)
    assert result.outputs["snapshot_path"] == expected_path


def test_default_snapshot_dir_es_home_tilde() -> None:
    """ADR-042 fix: el default debe ser `~/wcm-snapshots` (home user SSH),
    no /var/backups que requiere root y rompe en WHM/cPanel."""
    assert DEFAULT_SNAPSHOT_DIR == "~/wcm-snapshots"


def test_env_override_snapshot_dir(monkeypatch) -> None:
    """WCM_REMOTE_SNAPSHOT_DIR sobreescribe el default."""
    monkeypatch.setenv("WCM_REMOTE_SNAPSHOT_DIR", "/custom/path")
    agent = PreDeploySnapshotAgent(wp_config=_wp_config())
    project = _project_mock()
    ctx = _ctx(project)

    captured: dict[str, str] = {}

    async def _fake_snapshot(wp_config, dir_template, project_id):
        captured["dir"] = dir_template
        return f"{dir_template}/project-{project_id}-test.sql"

    with patch.object(
        PreDeploySnapshotAgent, "_snapshot", new=AsyncMock(side_effect=_fake_snapshot)
    ):
        agent.run(ctx)

    assert captured["dir"] == "/custom/path"


def test_ssh_error_se_envuelve_en_predeploysnapshoterror() -> None:
    agent = PreDeploySnapshotAgent(wp_config=_wp_config())
    project = _project_mock()
    ctx = _ctx(project)

    with patch.object(
        PreDeploySnapshotAgent,
        "_snapshot",
        new=AsyncMock(side_effect=WpSshConnectionError("connection refused")),
    ):
        with pytest.raises(PreDeploySnapshotError, match="connection refused"):
            agent.run(ctx)


def test_wpcli_error_se_envuelve() -> None:
    agent = PreDeploySnapshotAgent(wp_config=_wp_config())
    project = _project_mock()
    ctx = _ctx(project)

    with patch.object(
        PreDeploySnapshotAgent,
        "_snapshot",
        new=AsyncMock(
            side_effect=WpCliExecutionError(
                "wp db export → exit 1",
                exit_code=1,
                stdout="",
                stderr="disk full",
            )
        ),
    ):
        with pytest.raises(PreDeploySnapshotError, match="exit 1"):
            agent.run(ctx)
