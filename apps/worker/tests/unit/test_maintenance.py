"""Tests del task de retention sweep."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from wcm_worker.tasks.maintenance import (
    _move_outreach_to_discarded,
    _purge_error_logs,
    _purge_old_discarded,
    _purge_stale_discovered,
)


def _result_with_rowcount(n: int) -> MagicMock:
    r = MagicMock()
    r.rowcount = n
    return r


def test_purge_stale_discovered_returns_rowcount() -> None:
    session = MagicMock()
    session.execute.return_value = _result_with_rowcount(7)
    now = datetime.now(UTC)
    assert _purge_stale_discovered(session, now) == 7
    session.execute.assert_called_once()


def test_move_outreach_to_discarded_returns_rowcount() -> None:
    session = MagicMock()
    session.execute.return_value = _result_with_rowcount(3)
    now = datetime.now(UTC)
    assert _move_outreach_to_discarded(session, now) == 3


def test_purge_old_discarded_returns_rowcount() -> None:
    session = MagicMock()
    session.execute.return_value = _result_with_rowcount(2)
    now = datetime.now(UTC)
    assert _purge_old_discarded(session, now) == 2


def test_purge_error_logs_returns_rowcount() -> None:
    session = MagicMock()
    session.execute.return_value = _result_with_rowcount(10)
    now = datetime.now(UTC)
    assert _purge_error_logs(session, now) == 10


def test_retention_sweep_task_returns_aggregated_stats() -> None:
    from contextlib import contextmanager

    from wcm_worker.tasks import maintenance as mod

    session = MagicMock()

    @contextmanager
    def _fake_scope():
        yield session

    with patch.object(mod, "session_scope", _fake_scope), \
         patch.object(mod, "_purge_stale_discovered", return_value=1), \
         patch.object(mod, "_move_outreach_to_discarded", return_value=2), \
         patch.object(mod, "_purge_old_discarded", return_value=3), \
         patch.object(mod, "_purge_error_logs", return_value=4):
        result = mod.retention_sweep.apply().get()
    assert result["status"] == "ok"
    assert result["stats"] == {
        "leads_discovered_purged": 1,
        "leads_outreach_to_discarded": 2,
        "leads_discarded_purged": 3,
        "error_logs_purged": 4,
    }
    session.add.assert_called_once()
