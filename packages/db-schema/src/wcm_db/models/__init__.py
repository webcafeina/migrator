"""Modelos SQLAlchemy importados aquí para que Alembic los descubra todos
al cargar `wcm_db.models`.
"""

from wcm_db.models.assets import Asset
from wcm_db.models.audit import AuditLog, ErrorLog
from wcm_db.models.bricks_pages import BricksPage
from wcm_db.models.campaigns import Campaign
from wcm_db.models.content_blocks import ContentBlock
from wcm_db.models.leads import Lead, LeadEnrichment, OptOutLog
from wcm_db.models.outreach import (
    EmailLayout,
    OutreachSend,
    OutreachSequence,
    OutreachTemplate,
)
from wcm_db.models.projects import Project, ProjectPhase
from wcm_db.models.qa_reports import QaReport
from wcm_db.models.residual_tasks import ResidualTask
from wcm_db.models.scraped_pages import ScrapedPage
from wcm_db.models.seo_redirects import SeoRedirect
from wcm_db.models.users import User
from wcm_db.models.visual_diffs import VisualDiff
from wcm_db.models.woo_orders import WooOrder
from wcm_db.models.woo_products import WooProduct

__all__ = [
    "Asset",
    "AuditLog",
    "BricksPage",
    "Campaign",
    "ContentBlock",
    "EmailLayout",
    "ErrorLog",
    "Lead",
    "LeadEnrichment",
    "OptOutLog",
    "OutreachSend",
    "OutreachSequence",
    "OutreachTemplate",
    "Project",
    "ProjectPhase",
    "QaReport",
    "ResidualTask",
    "ScrapedPage",
    "SeoRedirect",
    "User",
    "VisualDiff",
    "WooOrder",
    "WooProduct",
]
