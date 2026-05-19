"""Subagentes operativos del producto.

Cada subagente implementa la interfaz `BaseAgent`. Algunos son
implementaciones reales (envuelven los paquetes ya construidos), otros
son stubs documentados que se implementan en fases posteriores.
"""

from wcm_worker.agents.asset_optimizer import AssetOptimizerAgent
from wcm_worker.agents.base import AgentContext, AgentResult, BaseAgent
from wcm_worker.agents.bricks_transpiler import BricksTranspilerAgent
from wcm_worker.agents.checklist_generator import ChecklistGeneratorAgent
from wcm_worker.agents.clickup_syncer import ClickupSyncerAgent
from wcm_worker.agents.content_extractor import ContentExtractorAgent
from wcm_worker.agents.enricher import EnricherAgent
from wcm_worker.agents.fingerprinter import FingerprinterAgent
from wcm_worker.agents.forms_rebuilder import FormsRebuilderAgent
from wcm_worker.agents.multilang_handler import MultilangHandlerAgent
from wcm_worker.agents.outreach_composer import OutreachComposerAgent
from wcm_worker.agents.outreach_sender import OutreachSenderAgent
from wcm_worker.agents.prospector import ProspectorAgent
from wcm_worker.agents.qa_runner import QaRunnerAgent
from wcm_worker.agents.resend_notifier import ResendNotifierAgent
from wcm_worker.agents.rollback import RollbackAgent
from wcm_worker.agents.scraper_origin import ScraperOriginAgent
from wcm_worker.agents.seo_preserver import SeoPreserverAgent
from wcm_worker.agents.visual_diff import VisualDiffAgent
from wcm_worker.agents.woo_migrator import WooMigratorAgent
from wcm_worker.agents.wp_deployer import WpDeployerAgent
from wcm_worker.agents.wpml_configurator import WpmlConfiguratorAgent

__all__ = [
    "AgentContext",
    "AgentResult",
    "AssetOptimizerAgent",
    "BaseAgent",
    "BricksTranspilerAgent",
    "ChecklistGeneratorAgent",
    "ClickupSyncerAgent",
    "ContentExtractorAgent",
    "EnricherAgent",
    "FingerprinterAgent",
    "FormsRebuilderAgent",
    "MultilangHandlerAgent",
    "OutreachComposerAgent",
    "OutreachSenderAgent",
    "ProspectorAgent",
    "QaRunnerAgent",
    "ResendNotifierAgent",
    "RollbackAgent",
    "ScraperOriginAgent",
    "SeoPreserverAgent",
    "VisualDiffAgent",
    "WooMigratorAgent",
    "WpDeployerAgent",
    "WpmlConfiguratorAgent",
]
