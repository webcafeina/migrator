"""Tests del ProspectorAgent — Google Places mockeado, DB con MagicMock.

Cubrimos: requisitos del ctx, deduplicación vía conflict, filtros
(no_website, blocked_type, exclude_domains), normalización de URL,
manejo de quota como warning no-bloqueante.
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

from wcm_scraper_core.directories.google_places import (
    GooglePlacesQuotaExceeded,
    PlaceResult,
)
from wcm_scraper_core.urls import normalize_lead_url as _normalize_url
from wcm_worker.agents.base import AgentContext
from wcm_worker.agents.prospector import (
    ProspectorAgent,
    _domain_of,
)
from wcm_worker.errors import ProspectorError

# ---------- helpers ----------

def _place(
    *,
    place_id: str = "p1",
    name: str = "Bar Pepe",
    website: str | None = "https://barpepe.es/",
    phone: str | None = "+34666111222",
    types: tuple[str, ...] = ("restaurant", "food"),
) -> PlaceResult:
    return PlaceResult(
        place_id=place_id,
        name=name,
        formatted_address="Calle Mayor, Cáceres",
        website=website,
        phone=phone,
        rating=4.2,
        user_ratings_total=10,
        types=types,
        raw={},
    )


class _FakeClient:
    """Cliente fake del Google Places que sirve una lista predefinida.

    `place_details(id)` devuelve el mismo PlaceResult (Text Search legacy
    no incluye `website`/`phone`, en producción se piden con un segundo
    call; el fake simplifica devolviendo el ya enriquecido).
    """

    def __init__(self, places: list[PlaceResult] | Iterator[PlaceResult] | None = None,
                 *, raises: Exception | None = None) -> None:
        self._places = list(places) if places else []
        self._raises = raises
        self.closed = False
        self.details_calls: list[str] = []

    def text_search(self, query: str, *, max_pages: int = 3):
        if self._raises:
            raise self._raises
        yield from self._places

    def place_details(self, place_id: str) -> PlaceResult | None:
        self.details_calls.append(place_id)
        for p in self._places:
            if p.place_id == place_id:
                return p
        return None

    def close(self) -> None:
        self.closed = True


def _setup_upsert_mock(fake_session, *, returned_ids: list[int | None]) -> None:
    """Mockea session.execute para devolver scalar_one_or_none con los IDs dados."""
    scalars = []
    for id_ in returned_ids:
        m = MagicMock()
        m.scalar_one_or_none.return_value = id_
        scalars.append(m)
    fake_session.execute.side_effect = scalars


# ---------- tests ----------

def test_prospector_requires_sector_and_region(fake_session) -> None:
    agent = ProspectorAgent(client=_FakeClient())
    with pytest.raises(ProspectorError, match="sector"):
        agent.run(AgentContext(session=fake_session, extra={"region": "Madrid"}))


def test_prospector_creates_one_lead_per_unique_website(fake_session) -> None:
    places = [_place(place_id="p1", website="https://a.com"),
              _place(place_id="p2", website="https://b.com")]
    _setup_upsert_mock(fake_session, returned_ids=[10, 11])

    agent = ProspectorAgent(client=_FakeClient(places))
    result = agent.run(
        AgentContext(
            session=fake_session,
            extra={"sector": "bar", "region": "Cáceres", "target_count": 10},
        )
    )

    assert result.outputs["discovered"] == 2
    assert result.outputs["created"] == 2
    # 2 enrichments + 2 audit_log → 4 adds
    assert fake_session.add.call_count == 4


def test_prospector_skips_places_without_website(fake_session) -> None:
    places = [_place(place_id="p1", website=None), _place(place_id="p2", website="https://x.com")]
    _setup_upsert_mock(fake_session, returned_ids=[1])

    agent = ProspectorAgent(client=_FakeClient(places))
    result = agent.run(
        AgentContext(
            session=fake_session,
            extra={"sector": "x", "region": "y", "target_count": 5},
        )
    )

    assert result.outputs["skipped_no_website"] == 1
    assert result.outputs["created"] == 1


def test_prospector_blocked_types_skip(fake_session) -> None:
    places = [_place(types=("gas_station",)), _place(types=("restaurant",))]
    _setup_upsert_mock(fake_session, returned_ids=[1])

    agent = ProspectorAgent(client=_FakeClient(places))
    result = agent.run(
        AgentContext(
            session=fake_session,
            extra={"sector": "x", "region": "y"},
        )
    )
    assert result.outputs["skipped_blocked_type"] == 1
    assert result.outputs["created"] == 1


def test_prospector_exclude_domains(fake_session) -> None:
    places = [
        _place(place_id="p1", website="https://blacklisted.com/foo"),
        _place(place_id="p2", website="https://allowed.com/"),
    ]
    _setup_upsert_mock(fake_session, returned_ids=[1])

    agent = ProspectorAgent(client=_FakeClient(places))
    result = agent.run(
        AgentContext(
            session=fake_session,
            extra={
                "sector": "x", "region": "y",
                "exclude_domains": ["blacklisted.com"],
            },
        )
    )
    assert result.outputs["skipped_excluded"] == 1
    assert result.outputs["created"] == 1


def test_prospector_counts_duplicates(fake_session) -> None:
    places = [_place(website="https://dup.com"), _place(website="https://new.com")]
    # Primer upsert: conflict (None); segundo: nuevo (id=99)
    _setup_upsert_mock(fake_session, returned_ids=[None, 99])

    agent = ProspectorAgent(client=_FakeClient(places))
    result = agent.run(
        AgentContext(session=fake_session, extra={"sector": "x", "region": "y"}),
    )
    assert result.outputs["skipped_duplicate"] == 1
    assert result.outputs["created"] == 1


def test_prospector_quota_exceeded_is_warning_not_error(fake_session) -> None:
    client = _FakeClient(raises=GooglePlacesQuotaExceeded("OVER_QUERY_LIMIT", "x"))
    agent = ProspectorAgent(client=client)
    result = agent.run(
        AgentContext(session=fake_session, extra={"sector": "x", "region": "y"})
    )
    assert any("Quota" in w for w in result.warnings)
    assert result.outputs["created"] == 0


def test_prospector_respects_target_count(fake_session) -> None:
    places = [_place(place_id=f"p{i}", website=f"https://x{i}.com") for i in range(10)]
    _setup_upsert_mock(fake_session, returned_ids=[i + 1 for i in range(3)])

    agent = ProspectorAgent(client=_FakeClient(places))
    result = agent.run(
        AgentContext(
            session=fake_session,
            extra={"sector": "x", "region": "y", "target_count": 3},
        )
    )
    assert result.outputs["discovered"] == 3
    assert result.outputs["created"] == 3


def test_prospector_missing_env_when_no_client_injected(fake_session, monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    agent = ProspectorAgent()  # sin client → intentará leer env
    with pytest.raises(ProspectorError, match="GOOGLE_MAPS_API_KEY"):
        agent.run(
            AgentContext(session=fake_session, extra={"sector": "x", "region": "y"})
        )


def test_prospector_returns_created_lead_ids(fake_session) -> None:
    """WCM-026: outputs incluye la lista de lead_ids creados para que la
    task pueda encadenar fingerprint + enrich por cada uno."""
    places = [_place(place_id="p1", website="https://a.com"),
              _place(place_id="p2", website="https://b.com")]
    _setup_upsert_mock(fake_session, returned_ids=[10, 11])

    agent = ProspectorAgent(client=_FakeClient(places))
    result = agent.run(
        AgentContext(
            session=fake_session,
            extra={"sector": "x", "region": "y", "target_count": 10},
        )
    )

    assert result.outputs["created_lead_ids"] == [10, 11]


def test_prospector_skips_when_details_returns_no_website(fake_session) -> None:
    """Place sin website tras consultar place_details → se descarta."""
    places = [_place(place_id="p1", website=None)]  # ni base ni details devolverán website
    _setup_upsert_mock(fake_session, returned_ids=[])

    agent = ProspectorAgent(client=_FakeClient(places))
    result = agent.run(
        AgentContext(session=fake_session, extra={"sector": "x", "region": "y"})
    )

    assert result.outputs["skipped_no_website"] == 1
    assert result.outputs["created"] == 0
    assert result.outputs["created_lead_ids"] == []


def test_normalize_url_drops_www_and_trailing_slash() -> None:
    assert _normalize_url("https://www.Example.com/") == "https://example.com/"
    assert _normalize_url("Example.com/contacto/") == "https://example.com/contacto"


def test_domain_of_strips_www() -> None:
    assert _domain_of("https://www.example.com/foo") == "example.com"
    assert _domain_of("https://example.com/") == "example.com"
