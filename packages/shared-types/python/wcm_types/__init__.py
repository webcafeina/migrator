"""Schemas Pydantic v2 compartidos entre API y dashboard.

Estos schemas son la fuente de la verdad para los tipos TS generados a
`packages/shared-types/ts/`. Importan los enums desde wcm_db para evitar
duplicación.

Cada entidad expone:
- `XxxBase`: campos comunes (validación)
- `XxxCreate`: payload de creación (subset)
- `XxxRead`: respuesta de API (incluye id, timestamps, etc.)
"""

from wcm_types.enums import (
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
from wcm_types.schemas.assets import AssetCreate, AssetRead
from wcm_types.schemas.audit import AuditLogRead, ErrorLogRead
from wcm_types.schemas.bricks_pages import BricksPageRead
from wcm_types.schemas.content_blocks import ContentBlockCreate, ContentBlockRead
from wcm_types.schemas.leads import (
    LeadCreate,
    LeadEnrichmentCreate,
    LeadEnrichmentRead,
    LeadRead,
    LeadUpdate,
    OptOutLogRead,
)
from wcm_types.schemas.outreach import (
    OutreachSendRead,
    OutreachSequenceCreate,
    OutreachSequenceRead,
)
from wcm_types.schemas.projects import (
    ProjectCreate,
    ProjectPhaseRead,
    ProjectRead,
    ProjectUpdate,
)
from wcm_types.schemas.residual_tasks import ResidualTaskCreate, ResidualTaskRead
from wcm_types.schemas.scraped_pages import ScrapedPageRead
from wcm_types.schemas.seo_redirects import SeoRedirectRead
from wcm_types.schemas.users import UserCreate, UserRead
from wcm_types.schemas.woo_products import WooProductRead

__all__ = [
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
    # schemas
    "AssetCreate",
    "AssetRead",
    "AuditLogRead",
    "BricksPageRead",
    "ContentBlockCreate",
    "ContentBlockRead",
    "ErrorLogRead",
    "LeadCreate",
    "LeadEnrichmentCreate",
    "LeadEnrichmentRead",
    "LeadRead",
    "LeadUpdate",
    "OptOutLogRead",
    "OutreachSendRead",
    "OutreachSequenceCreate",
    "OutreachSequenceRead",
    "ProjectCreate",
    "ProjectPhaseRead",
    "ProjectRead",
    "ProjectUpdate",
    "ResidualTaskCreate",
    "ResidualTaskRead",
    "ScrapedPageRead",
    "SeoRedirectRead",
    "UserCreate",
    "UserRead",
    "WooProductRead",
]
