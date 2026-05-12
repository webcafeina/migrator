"""Webcafeína Migrator — paquete de modelos SQLAlchemy 2.x y schema PostgreSQL.

Fuente única de la verdad para el modelo de datos del sistema. Importa
`Base` para registrar metadata, o un modelo concreto para usarlo en CRUD.
"""

from wcm_db.base import Base
from wcm_db.enums import (
    AssetStatus,
    AuditAction,
    BlockType,
    BuilderType,
    ContentBlockSource,
    ErrorSeverity,
    LeadStatus,
    OutreachChannel,
    OutreachSendStatus,
    OutreachSequenceStatus,
    ProjectPhaseStatus,
    ProjectStatus,
    ResidualCategory,
    ResidualStatus,
    ScrapeStatus,
    UserRole,
)
from wcm_db.models.assets import Asset
from wcm_db.models.audit import AuditLog, ErrorLog
from wcm_db.models.bricks_pages import BricksPage
from wcm_db.models.content_blocks import ContentBlock
from wcm_db.models.leads import Lead, LeadEnrichment, OptOutLog
from wcm_db.models.outreach import OutreachSend, OutreachSequence
from wcm_db.models.projects import Project, ProjectPhase
from wcm_db.models.scraped_pages import ScrapedPage
from wcm_db.models.seo_redirects import SeoRedirect
from wcm_db.models.users import User
from wcm_db.models.woo_products import WooProduct
from wcm_db.models.residual_tasks import ResidualTask

__all__ = [
    "Base",
    # enums
    "AssetStatus",
    "AuditAction",
    "BlockType",
    "BuilderType",
    "ContentBlockSource",
    "ErrorSeverity",
    "LeadStatus",
    "OutreachChannel",
    "OutreachSendStatus",
    "OutreachSequenceStatus",
    "ProjectPhaseStatus",
    "ProjectStatus",
    "ResidualCategory",
    "ResidualStatus",
    "ScrapeStatus",
    "UserRole",
    # models
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
