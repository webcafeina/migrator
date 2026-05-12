"""Modelos SQLAlchemy importados aquí para que Alembic los descubra todos
al cargar `wcm_db.models`.
"""

from wcm_db.models.assets import Asset
from wcm_db.models.audit import AuditLog, ErrorLog
from wcm_db.models.bricks_pages import BricksPage
from wcm_db.models.content_blocks import ContentBlock
from wcm_db.models.leads import Lead, LeadEnrichment, OptOutLog
from wcm_db.models.outreach import OutreachSend, OutreachSequence
from wcm_db.models.projects import Project, ProjectPhase
from wcm_db.models.residual_tasks import ResidualTask
from wcm_db.models.scraped_pages import ScrapedPage
from wcm_db.models.seo_redirects import SeoRedirect
from wcm_db.models.users import User
from wcm_db.models.woo_products import WooProduct

__all__ = [
    "Asset",
    "AuditLog",
    "BricksPage",
    "ContentBlock",
    "ErrorLog",
    "Lead",
    "LeadEnrichment",
    "OptOutLog",
    "OutreachSend",
    "OutreachSequence",
    "Project",
    "ProjectPhase",
    "ResidualTask",
    "ScrapedPage",
    "SeoRedirect",
    "User",
    "WooProduct",
]
