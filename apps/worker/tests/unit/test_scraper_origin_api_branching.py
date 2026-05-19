"""Tests del branching API ↔ Playwright en ScraperOriginAgent (v0.18.0).

Aísla `_seed_from_api` y verifica:
- Sin source_access_mode='api' → [] (sin tocar adapter).
- Sin credenciales encriptadas → [].
- Credenciales no descifrables → [] + warning logueado.
- Wix adapter falla con WixApiError → [] (fallback seguro).
- Wix adapter OK → URLs canónicas.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from cryptography.fernet import Fernet

from wcm_worker.agents.scraper_origin import ScraperOriginAgent
from wcm_worker.integrations.wix_api import WixApiAuthError, WixPageInfo


def _project_mock(
    *,
    access_mode: str = "none",
    encrypted: str | None = None,
    builder: str | None = "wix",
) -> MagicMock:
    p = MagicMock()
    p.id = 7
    p.source_access_mode = access_mode
    p.source_credentials_encrypted = encrypted
    if builder:
        p.builder_source = MagicMock(value=builder)
    else:
        p.builder_source = None
    return p


def test_seed_vacio_si_modo_no_api() -> None:
    agent = ScraperOriginAgent()
    project = _project_mock(access_mode="none")
    assert agent._seed_from_api(project) == []


def test_seed_vacio_si_sin_credenciales() -> None:
    agent = ScraperOriginAgent()
    project = _project_mock(access_mode="api", encrypted=None)
    assert agent._seed_from_api(project) == []


def test_seed_vacio_si_credenciales_no_descifran(monkeypatch) -> None:
    """FERNET_KEY ausente → CredentialsDecryptError → fallback []."""
    monkeypatch.delenv("FERNET_KEY", raising=False)
    agent = ScraperOriginAgent()
    project = _project_mock(access_mode="api", encrypted="ciphertext-fake")
    assert agent._seed_from_api(project) == []


def test_seed_devuelve_urls_si_wix_responde_ok(monkeypatch) -> None:
    """Wix adapter OK → URLs canónicas pasadas al BFS."""
    import json

    key = Fernet.generate_key()
    monkeypatch.setenv("FERNET_KEY", key.decode())
    fernet = Fernet(key)
    creds_plain = {"api_key": "k" * 30, "site_id": "site-1234abcd"}
    ciphertext = fernet.encrypt(json.dumps(creds_plain).encode()).decode()

    fake_urls = ["https://miweb.com/", "https://miweb.com/contacto"]

    async def _fake_fetch(_builder, _creds):
        return fake_urls

    agent = ScraperOriginAgent()
    project = _project_mock(access_mode="api", encrypted=ciphertext, builder="wix")

    with patch.object(
        ScraperOriginAgent, "_fetch_api_urls", new=AsyncMock(side_effect=_fake_fetch)
    ):
        urls = agent._seed_from_api(project)

    assert urls == fake_urls


def test_seed_fallback_si_wix_api_falla(monkeypatch) -> None:
    """Wix adapter levanta WixApiAuthError → fallback [] (sin propagar)."""
    import json

    from cryptography.fernet import Fernet as _Fernet

    key = Fernet.generate_key()
    monkeypatch.setenv("FERNET_KEY", key.decode())
    fernet = _Fernet(key)
    creds_plain = {"api_key": "bad-key", "site_id": "site-1234abcd"}
    ciphertext = fernet.encrypt(json.dumps(creds_plain).encode()).decode()

    agent = ScraperOriginAgent()
    project = _project_mock(access_mode="api", encrypted=ciphertext, builder="wix")

    async def _fake_fetch(_builder, _creds):
        raise WixApiAuthError("401 invalid")

    with patch.object(ScraperOriginAgent, "_fetch_api_urls", new=AsyncMock(side_effect=_fake_fetch)):
        urls = agent._seed_from_api(project)

    assert urls == []


def test_seed_vacio_si_builder_no_soportado(monkeypatch) -> None:
    """Builder distinto a wix/webflow → adapter no se llama, [] silencioso."""
    import json

    from cryptography.fernet import Fernet as _Fernet

    key = Fernet.generate_key()
    monkeypatch.setenv("FERNET_KEY", key.decode())
    fernet = _Fernet(key)
    ciphertext = fernet.encrypt(json.dumps({"api_key": "x"}).encode()).decode()

    agent = ScraperOriginAgent()
    project = _project_mock(access_mode="api", encrypted=ciphertext, builder="squarespace")
    assert agent._seed_from_api(project) == []
