"""E2E del pipeline de migración completa.

Estrategia: instanciamos el `Orchestrator` con un sub-set de fases que
representa el flujo crítico Wix → Bricks, y verificamos que cada fase
genera los efectos esperados sobre el estado.

Lo que NO toca:
- Red real (httpx mockeado para fetch del Wix HTML).
- Postgres real (session stateful en memoria, fixture en conftest).
- R2 / Resend / ClickUp (skipped sin credenciales).
- Playwright (sólo HTML simple para fingerprinting).

Esto es e2e *del pipeline*, no e2e *del sistema completo* (que requeriría
servidor WP real, R2 real, etc. — eso es post-MVP).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wcm_db.models.bricks_pages import BricksPage
from wcm_db.models.residual_tasks import ResidualTask
from wcm_db.models.scraped_pages import ScrapedPage
from wcm_types.enums import ProjectStatus, ResidualCategory, ResidualStatus
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.pipeline import Orchestrator, _PhaseSpec


# ---------- Stub agents que replican el comportamiento real ----------

class _ScraperOriginStub(BaseAgent):
    name = "scraper-origin"
    phase_name = "scrape_origin"

    def run(self, ctx: AgentContext) -> AgentResult:
        # Simula scrapeo: crea ScrapedPage real en la session stateful.
        ctx.session.add(
            ScrapedPage(
                project_id=ctx.project_id,
                url="https://barpepe.es",
                title="Bar Pepe",
                html_raw="<html>...</html>",
                depth=0,
            )
        )
        return AgentResult(summary="1 página scrapeada", outputs={"pages": 1})


class _ContentExtractorStub(BaseAgent):
    name = "content-extractor"
    phase_name = "extract_content"

    def run(self, ctx: AgentContext) -> AgentResult:
        return AgentResult(summary="6 bloques extraídos", outputs={"blocks": 6})


class _SeoPreserverStub(BaseAgent):
    name = "seo-preserver"
    phase_name = "preserve_seo"

    def run(self, ctx: AgentContext) -> AgentResult:
        return AgentResult(
            summary="meta+og+canonical preservados",
            outputs={"meta_count": 3, "redirects": 0},
        )


class _BricksTranspilerStub(BaseAgent):
    name = "bricks-transpiler"
    phase_name = "transpile_bricks"

    def run(self, ctx: AgentContext) -> AgentResult:
        ctx.session.add(
            BricksPage(
                project_id=ctx.project_id,
                page_id=1,
                slug="home",
                title="Bar Pepe",
                bricks_json={"content": []},
            )
        )
        return AgentResult(summary="home → bricks JSON", outputs={"pages": 1})


class _WpDeployerStub(BaseAgent):
    name = "wp-deployer"
    phase_name = "deploy_wp"

    def run(self, ctx: AgentContext) -> AgentResult:
        return AgentResult(summary="WP listo, 1 página subida", outputs={"deployed": True})


class _ChecklistGeneratorStub(BaseAgent):
    name = "checklist-generator"
    phase_name = "generate_checklist"

    def run(self, ctx: AgentContext) -> AgentResult:
        for i in range(3):
            ctx.session.add(
                ResidualTask(
                    project_id=ctx.project_id,
                    title=f"Tarea residual {i}",
                    description="Pendiente de revisión humana",
                    category=ResidualCategory.CLIENT_CONFIG,
                    status=ResidualStatus.OPEN,
                )
            )
        return AgentResult(
            summary="3 tareas residuales",
            outputs={"created": 3, "residual_tasks_created": 3},
        )


# ---------- E2E tests ----------

def test_e2e_minimal_migration_pipeline_succeeds(stateful_session: MagicMock) -> None:
    """Pipeline mínimo Wix→Bricks: 5 fases obligatorias + checklist."""
    project = MagicMock()
    project.id = 42
    project.has_ecommerce = False
    project.is_multilang = False
    project.status = ProjectStatus.QUEUED
    project.started_at = None
    project.completed_at = None

    # `session.get(Project, 42)` debe devolver `project`. `session.get`
    # del stateful_session sólo busca lo añadido con `add`, así que
    # patcheamos el side_effect para que devuelva nuestro project.
    original_get = stateful_session.get.side_effect

    def _get(model: type, id_: object) -> object | None:
        if model.__name__ == "Project" and id_ == 42:
            return project
        return original_get(model, id_)

    stateful_session.get.side_effect = _get

    phases = (
        _PhaseSpec("scrape_origin", _ScraperOriginStub),
        _PhaseSpec("extract_content", _ContentExtractorStub),
        _PhaseSpec("preserve_seo", _SeoPreserverStub),
        _PhaseSpec("transpile_bricks", _BricksTranspilerStub),
        _PhaseSpec("deploy_wp", _WpDeployerStub),
        _PhaseSpec("generate_checklist", _ChecklistGeneratorStub, required=False),
    )
    orchestrator = Orchestrator(stateful_session, phases=phases)

    outcome = orchestrator.run_project(42)

    # Estado del proyecto
    assert outcome.final_status == ProjectStatus.COMPLETED
    assert outcome.failed_phase is None
    assert outcome.completed_phases == [
        "scrape_origin", "extract_content", "preserve_seo",
        "transpile_bricks", "deploy_wp", "generate_checklist",
    ]

    # Persistencia: ScrapedPage + BricksPage + 3 ResidualTask
    storage = stateful_session._storage
    assert "ScrapedPage" in storage
    assert "BricksPage" in storage
    assert "ResidualTask" in storage
    assert len(storage["ResidualTask"]) == 3


def test_e2e_pipeline_failure_in_required_phase_blocks(stateful_session: MagicMock) -> None:
    """Un fallo en una fase requerida deja el proyecto en FAILED."""
    from wcm_worker.errors import BricksTranspilerError

    project = MagicMock()
    project.id = 42
    project.has_ecommerce = False
    project.is_multilang = False
    project.status = ProjectStatus.QUEUED
    project.started_at = None
    project.completed_at = None

    def _get(model: type, id_: object) -> object | None:
        if model.__name__ == "Project" and id_ == 42:
            return project
        return None

    stateful_session.get.side_effect = _get

    class _FailingTranspiler(BaseAgent):
        name = "transpile-bricks"
        phase_name = "transpile_bricks"

        def run(self, ctx: AgentContext) -> AgentResult:
            raise BricksTranspilerError("schema mismatch")

    phases = (
        _PhaseSpec("scrape_origin", _ScraperOriginStub),
        _PhaseSpec("transpile_bricks", _FailingTranspiler),  # falla aquí
        _PhaseSpec("deploy_wp", _WpDeployerStub),  # no debe ejecutarse
    )
    outcome = Orchestrator(stateful_session, phases=phases).run_project(42)

    assert outcome.final_status == ProjectStatus.BLOCKED_HUMAN_INPUT
    assert outcome.failed_phase == "transpile_bricks"
    assert "scrape_origin" in outcome.completed_phases
    assert "deploy_wp" not in outcome.completed_phases


def test_e2e_optional_phase_failure_does_not_block(stateful_session: MagicMock) -> None:
    """Fallo en fase opcional: pipeline continúa, no marca FAILED."""
    from wcm_worker.errors import AssetOptimizerError

    project = MagicMock()
    project.id = 42
    project.has_ecommerce = False
    project.is_multilang = False
    project.status = ProjectStatus.QUEUED
    project.started_at = None
    project.completed_at = None

    def _get(model: type, id_: object) -> object | None:
        if model.__name__ == "Project" and id_ == 42:
            return project
        return None

    stateful_session.get.side_effect = _get

    class _FailingAssetOpt(BaseAgent):
        name = "asset-optimizer"
        phase_name = "optimize_assets"

        def run(self, ctx: AgentContext) -> AgentResult:
            raise AssetOptimizerError("R2 down")

    phases = (
        _PhaseSpec("scrape_origin", _ScraperOriginStub),
        _PhaseSpec("optimize_assets", _FailingAssetOpt, required=False),
        _PhaseSpec("deploy_wp", _WpDeployerStub),
    )
    outcome = Orchestrator(stateful_session, phases=phases).run_project(42)

    # El pipeline NO se bloquea, pero el outcome es QA_FAILED para
    # señalar que hay revisión humana pendiente sobre la fase no-required.
    assert outcome.final_status == ProjectStatus.QA_FAILED
    assert outcome.failed_phase == "optimize_assets"
    assert "scrape_origin" in outcome.completed_phases
    assert "deploy_wp" in outcome.completed_phases


def test_e2e_conditional_phase_skipped(stateful_session: MagicMock) -> None:
    """Fase con `condition_attr` que evalúa a False se salta."""
    project = MagicMock()
    project.id = 42
    project.has_ecommerce = False  # → migrate_woo skip
    project.is_multilang = False   # → configure_wpml skip
    project.status = ProjectStatus.QUEUED
    project.started_at = None
    project.completed_at = None

    def _get(model: type, id_: object) -> object | None:
        if model.__name__ == "Project" and id_ == 42:
            return project
        return None

    stateful_session.get.side_effect = _get

    class _ShouldNotRun(BaseAgent):
        name = "should-not-run"
        phase_name = "migrate_woo"

        def run(self, ctx: AgentContext) -> AgentResult:
            pytest.fail("Esta fase no debería ejecutarse con has_ecommerce=False")

    phases = (
        _PhaseSpec("scrape_origin", _ScraperOriginStub),
        _PhaseSpec("migrate_woo", _ShouldNotRun, required=False, condition_attr="has_ecommerce"),
        _PhaseSpec("deploy_wp", _WpDeployerStub),
    )
    outcome = Orchestrator(stateful_session, phases=phases).run_project(42)

    assert outcome.final_status == ProjectStatus.COMPLETED
    assert "migrate_woo" in outcome.skipped_phases
    assert "scrape_origin" in outcome.completed_phases
    assert "deploy_wp" in outcome.completed_phases


def test_e2e_fingerprinter_on_real_wix_html(wix_html: str) -> None:
    """Smoke real: el fingerprint del scraper-core clasifica el HTML de
    fixture como WIX con alta confianza.
    """
    from wcm_scraper_core.fingerprint import fingerprint_url

    result = fingerprint_url(html=wix_html, headers={})
    best = result.best_builder()
    assert best is not None
    assert best.name.lower() == "wix"
    assert best.confidence > 0.7, f"Confianza baja: {best.confidence}"
