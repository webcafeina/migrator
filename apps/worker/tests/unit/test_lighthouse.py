"""Tests del wrapper lighthouse (v0.16.0)."""

from __future__ import annotations

from unittest.mock import patch

from wcm_worker.integrations.lighthouse import (
    LighthouseResult,
    _extract_score,
    lighthouse_available,
    run_lighthouse,
)


def test_extract_score_normal() -> None:
    assert _extract_score({"score": 0.85}) == 85
    assert _extract_score({"score": 0.50}) == 50
    assert _extract_score({"score": 1.0}) == 100
    assert _extract_score({"score": 0.0}) == 0


def test_extract_score_none() -> None:
    assert _extract_score({"score": None}) is None
    assert _extract_score({}) is None
    assert _extract_score(None) is None


def test_lighthouse_available_uses_shutil_which() -> None:
    with patch("wcm_worker.integrations.lighthouse.shutil.which") as mock_which:
        mock_which.return_value = "/usr/local/bin/lighthouse"
        assert lighthouse_available() is True
        mock_which.return_value = None
        assert lighthouse_available() is False


def test_run_lighthouse_raises_if_not_available() -> None:
    """Sin binario `lighthouse` en PATH → LighthouseNotAvailableError."""
    from wcm_worker.integrations.lighthouse import LighthouseNotAvailableError

    with patch(
        "wcm_worker.integrations.lighthouse.lighthouse_available",
        return_value=False,
    ):
        import pytest

        with pytest.raises(LighthouseNotAvailableError, match="PATH"):
            run_lighthouse("https://example.com")


def test_run_lighthouse_parses_report_ok(tmp_path) -> None:
    """Mock subprocess + report file. Verifica parsing del JSON."""
    import json
    from subprocess import CompletedProcess

    fake_report = {
        "categories": {
            "performance": {"score": 0.92},
            "accessibility": {"score": 0.88},
            "best-practices": {"score": 0.95},
            "seo": {"score": 1.0},
        }
    }

    def _fake_run(args, **kwargs):
        # El path es args[args.index("--output-path") +0] aprox, mejor
        # buscar el `--output-path=...` y escribir ahí el report.
        for a in args:
            if a.startswith("--output-path="):
                target = a.split("=", 1)[1]
                with open(target, "w", encoding="utf-8") as f:
                    json.dump(fake_report, f)
                break
        return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    with (
        patch(
            "wcm_worker.integrations.lighthouse.lighthouse_available",
            return_value=True,
        ),
        patch("wcm_worker.integrations.lighthouse.subprocess.run", side_effect=_fake_run),
    ):
        result = run_lighthouse("https://example.com", form_factor="desktop")

    assert isinstance(result, LighthouseResult)
    assert result.performance == 92
    assert result.accessibility == 88
    assert result.best_practices == 95
    assert result.seo == 100
    assert result.raw_json is not None
