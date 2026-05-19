"""Tests del link_checker (v0.16.0)."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx

from wcm_worker.integrations.link_checker import BrokenLink, check_links


def _http_mock(responses: dict[str, MagicMock]) -> MagicMock:
    """Mock httpx.Client donde cada URL devuelve la response del dict."""
    client = MagicMock()

    def _get(url, **kwargs):
        if url not in responses:
            raise httpx.HTTPError(f"URL no mockeada: {url}")
        return responses[url]

    def _head(url, **kwargs):
        if url not in responses:
            raise httpx.HTTPError(f"URL no mockeada: {url}")
        return responses[url]

    client.get = MagicMock(side_effect=_get)
    client.head = MagicMock(side_effect=_head)
    return client


def _resp(*, status: int = 200, text: str = "") -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.text = text
    return r


def test_no_links_returns_empty_report() -> None:
    html = "<html><body>Sin links</body></html>"
    client = _http_mock({"https://target.es/": _resp(text=html)})
    report = check_links(["https://target.es/"], target_host="target.es", http_client=client)
    assert report.total_checked == 0
    assert report.broken_count == 0


def test_links_validos_no_aparecen_como_broken() -> None:
    html = '<html><body><a href="/contacto">Contacto</a></body></html>'
    client = _http_mock(
        {
            "https://target.es/": _resp(text=html),
            "https://target.es/contacto": _resp(status=200),
        }
    )
    report = check_links(["https://target.es/"], target_host="target.es", http_client=client)
    assert report.total_checked == 1
    assert report.broken_count == 0


def test_link_externo_se_ignora() -> None:
    html = '<html><a href="https://google.com">x</a></html>'
    client = _http_mock({"https://target.es/": _resp(text=html)})
    report = check_links(["https://target.es/"], target_host="target.es", http_client=client)
    # google.com NO es target.es → ignorado.
    assert report.total_checked == 0


def test_link_404_se_reporta_como_broken() -> None:
    html = '<html><a href="/no-existe">x</a></html>'
    client = _http_mock(
        {
            "https://target.es/": _resp(text=html),
            "https://target.es/no-existe": _resp(status=404),
        }
    )
    report = check_links(["https://target.es/"], target_host="target.es", http_client=client)
    assert report.total_checked == 1
    assert report.broken_count == 1
    assert isinstance(report.broken[0], BrokenLink)
    assert report.broken[0].url == "https://target.es/no-existe"
    assert report.broken[0].status_code == 404


def test_mailto_y_javascript_se_ignoran() -> None:
    html = (
        '<html><a href="mailto:a@b.es">e</a>'
        '<a href="javascript:void(0)">js</a>'
        '<a href="#x">anc</a></html>'
    )
    client = _http_mock({"https://target.es/": _resp(text=html)})
    report = check_links(["https://target.es/"], target_host="target.es", http_client=client)
    assert report.total_checked == 0


def test_dedupe_links_repetidos() -> None:
    """Mismo link aparecido en 2 pages cuenta como 1 check, pero
    source_pages refleja ambas páginas origen."""
    html_a = '<html><a href="/comun">x</a></html>'
    html_b = '<html><a href="/comun">y</a></html>'
    client = _http_mock(
        {
            "https://target.es/a": _resp(text=html_a),
            "https://target.es/b": _resp(text=html_b),
            "https://target.es/comun": _resp(status=500),
        }
    )
    report = check_links(
        ["https://target.es/a", "https://target.es/b"],
        target_host="target.es",
        http_client=client,
    )
    assert report.total_checked == 1  # dedupe
    assert report.broken_count == 1
    sources = set(report.broken[0].source_pages)
    assert sources == {"https://target.es/a", "https://target.es/b"}
