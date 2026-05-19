"""Tests del servicio `preflight` directamente (ADR-037 / v0.19.0+).

Verifica la lógica de agregación de blocking_issues + warnings, en particular
el comportamiento diferenciado de plugins: Bricks bloqueante, GF/WC informativos.
Mockea los 4 helpers internos para no tocar red.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from wcm_api.services.preflight import run_preflight
from wcm_types.schemas.projects import PreflightCheck


def _project_mock() -> MagicMock:
    p = MagicMock()
    p.id = 7
    p.source_url = "https://origen.test"
    p.source_access_mode = "none"
    p.source_credentials_encrypted = None
    p.builder_source = None
    return p


def _ok_check(msg: str = "ok", blocking: bool = True) -> PreflightCheck:
    return PreflightCheck(ok=True, blocking=blocking, message=msg)


def _fail_check(msg: str = "fail", blocking: bool = True) -> PreflightCheck:
    return PreflightCheck(ok=False, blocking=blocking, message=msg)


@pytest.mark.asyncio
async def test_bricks_faltante_bloquea_can_start(monkeypatch) -> None:
    """ADR-037: si Bricks NO está → blocking_issues incluye Bricks, can_start=False."""
    from wcm_api.services import preflight

    monkeypatch.setattr(preflight, "_check_wp_destination", AsyncMock(return_value=_ok_check()))
    monkeypatch.setattr(
        preflight, "_check_plugins",
        AsyncMock(return_value={"bricks": False, "gravity_forms": True, "woocommerce": True}),
    )
    monkeypatch.setattr(preflight, "_check_source", AsyncMock(return_value=_ok_check()))
    monkeypatch.setattr(
        preflight, "_check_source_credentials",
        AsyncMock(return_value=_ok_check(blocking=False)),
    )

    result = await run_preflight(_project_mock())

    assert result.can_start is False
    assert any("Bricks" in m for m in result.blocking_issues)
    # GF y WC presentes → no warnings de plugins.
    assert not any("Plugin gravity_forms" in w for w in result.warnings)
    assert not any("Plugin woocommerce" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_gf_y_wc_faltantes_solo_warnings(monkeypatch) -> None:
    """ADR-037: GF y WC ausentes son warnings, no bloquean."""
    from wcm_api.services import preflight

    monkeypatch.setattr(preflight, "_check_wp_destination", AsyncMock(return_value=_ok_check()))
    monkeypatch.setattr(
        preflight, "_check_plugins",
        AsyncMock(return_value={"bricks": True, "gravity_forms": False, "woocommerce": False}),
    )
    monkeypatch.setattr(preflight, "_check_source", AsyncMock(return_value=_ok_check()))
    monkeypatch.setattr(
        preflight, "_check_source_credentials",
        AsyncMock(return_value=_ok_check(blocking=False)),
    )

    result = await run_preflight(_project_mock())

    assert result.can_start is True
    assert not any("Bricks" in m for m in result.blocking_issues)
    assert any("gravity_forms" in w for w in result.warnings)
    assert any("woocommerce" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_todos_los_plugins_presentes(monkeypatch) -> None:
    """Sin warnings ni bloqueantes de plugins cuando los 3 responden."""
    from wcm_api.services import preflight

    monkeypatch.setattr(preflight, "_check_wp_destination", AsyncMock(return_value=_ok_check()))
    monkeypatch.setattr(
        preflight, "_check_plugins",
        AsyncMock(return_value={"bricks": True, "gravity_forms": True, "woocommerce": True}),
    )
    monkeypatch.setattr(preflight, "_check_source", AsyncMock(return_value=_ok_check()))
    monkeypatch.setattr(
        preflight, "_check_source_credentials",
        AsyncMock(return_value=_ok_check(blocking=False)),
    )

    result = await run_preflight(_project_mock())

    assert result.can_start is True
    assert not any("Plugin" in w for w in result.warnings)
    assert not any("Bricks" in m for m in result.blocking_issues)


@pytest.mark.asyncio
async def test_bricks_y_wp_destino_ambos_bloquean(monkeypatch) -> None:
    """Dos blocking_issues acumulados si Bricks y WP destino fallan."""
    from wcm_api.services import preflight

    monkeypatch.setattr(
        preflight, "_check_wp_destination",
        AsyncMock(return_value=_fail_check("REST: HTTP 502")),
    )
    monkeypatch.setattr(
        preflight, "_check_plugins",
        AsyncMock(return_value={"bricks": False, "gravity_forms": True, "woocommerce": True}),
    )
    monkeypatch.setattr(preflight, "_check_source", AsyncMock(return_value=_ok_check()))
    monkeypatch.setattr(
        preflight, "_check_source_credentials",
        AsyncMock(return_value=_ok_check(blocking=False)),
    )

    result = await run_preflight(_project_mock())

    assert result.can_start is False
    assert len(result.blocking_issues) == 2
    assert any("WP destino" in m for m in result.blocking_issues)
    assert any("Bricks" in m for m in result.blocking_issues)
