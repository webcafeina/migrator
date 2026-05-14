"""Tests del generador de IDs."""

from __future__ import annotations

import re

from wcm_bricks_transpiler.ids import IdGenerator, make_element_id

ID_PATTERN = re.compile(r"^[a-z0-9]{6}$")


def test_make_element_id_format() -> None:
    eid = make_element_id(project_id=1, page_id=1, order_index=0, block_type="hero")
    assert ID_PATTERN.match(eid), f"ID mal formado: {eid!r}"


def test_make_element_id_is_deterministic() -> None:
    a = make_element_id(1, 2, 3, "hero", sub_index=0)
    b = make_element_id(1, 2, 3, "hero", sub_index=0)
    assert a == b


def test_make_element_id_changes_with_any_input() -> None:
    base = make_element_id(1, 1, 0, "hero")
    variations = [
        make_element_id(2, 1, 0, "hero"),  # project
        make_element_id(1, 2, 0, "hero"),  # page
        make_element_id(1, 1, 1, "hero"),  # order
        make_element_id(1, 1, 0, "text"),  # type
        make_element_id(1, 1, 0, "hero", sub_index=1),  # sub
        make_element_id(1, 1, 0, "hero", salt="other"),  # salt
    ]
    for v in variations:
        assert v != base, f"ID no cambió al variar input: {v}"


def test_id_generator_unique_in_page() -> None:
    gen = IdGenerator(project_id=1, page_id=1)
    ids = [gen.fresh(order_index=i, block_type="hero") for i in range(100)]
    assert len(set(ids)) == 100, "IDs duplicados en página"


def test_id_generator_used_set_tracks_assigned() -> None:
    gen = IdGenerator(project_id=1, page_id=1)
    ids = {gen.fresh(order_index=0, block_type="hero", sub_index=i) for i in range(5)}
    assert ids == set(gen.used)
