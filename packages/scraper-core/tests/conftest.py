"""Fixtures comunes para tests de scraper-core."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load(path: str) -> str:
    return (FIXTURES_DIR / path).read_text(encoding="utf-8")


@pytest.fixture()
def wix_corporate_html() -> str:
    return _load("wix/corporate.html")


@pytest.fixture()
def hostinger_clinica_html() -> str:
    return _load("hostinger/clinica.html")


@pytest.fixture()
def webflow_agency_html() -> str:
    return _load("webflow/agency.html")
