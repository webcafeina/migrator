"""Fixtures comunes para tests del CLI."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner


@pytest.fixture(autouse=True)
def _isolate_state(monkeypatch, tmp_path: Path) -> Iterator[None]:
    """Aísla credenciales, env vars y modo JSON entre tests.

    También fija el ancho del terminal y desactiva colores ANSI para
    que el formato Rich de los errores de typer sea idéntico en local
    y en CI. Sin esto:
    - En local con terminal ancho (200+ cols), Rich no envuelve y
      `--confirm` cabe en una línea → `assert "--confirm" in output`
      pasa.
    - En CI (default 80 cols), Rich rompe `--confirm` entre líneas
      → el mismo assert falla.
    Reproducibilidad obligatoria para que `pnpm`/`pytest` local
    detecte lo mismo que la CI.
    """
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    import wcm_cli.config as cfg_mod
    monkeypatch.setattr(cfg_mod, "CREDENTIALS_DIR", fake_home / ".config" / "wcm")
    monkeypatch.setattr(
        cfg_mod, "CREDENTIALS_PATH", fake_home / ".config" / "wcm" / "credentials.json"
    )
    # Limpiar vars que pueden contaminar entre tests
    monkeypatch.delenv("WCM_TOKEN", raising=False)
    monkeypatch.delenv("WCM_JSON", raising=False)
    # Forzar terminal ancho + sin colores ANSI → mismo formato local/CI
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.setenv("LINES", "50")
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("TERM", "dumb")
    yield


@pytest.fixture()
def runner() -> CliRunner:
    # mix_stderr=True para capturar stderr (output.error) en el mismo buffer
    # que stdout — facilita assertions sobre output completo en tests.
    try:
        return CliRunner(mix_stderr=True)
    except TypeError:  # Typer >= 0.16 quita mix_stderr; ahora siempre mezcla
        return CliRunner()


@pytest.fixture()
def authenticated(monkeypatch) -> None:
    """Inyecta un token vía WCM_TOKEN para saltar el login."""
    monkeypatch.setenv("WCM_TOKEN", "fake-jwt-token-for-tests")


@pytest.fixture(autouse=True)
def _api_url(monkeypatch) -> None:
    monkeypatch.setenv("API_URL", "http://api.test")


@pytest.fixture(autouse=True)
def _disable_dotenv_autoload(monkeypatch) -> None:
    """Evita que CliConfig._autoload_dotenv lea el .env real del repo."""
    monkeypatch.chdir("/tmp")
