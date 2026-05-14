"""Re-export de los enums canónicos definidos en wcm_types.

Mantener este módulo permite que el código del backend importe desde
`wcm_db.enums` sin acoplar al paquete de tipos. La fuente única vive en
`wcm_types/enums.py`.
"""

from wcm_types.enums import (
    AssetStatus,
    AuditAction,
    BlockType,
    BuilderType,
    CampaignStatus,
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

__all__ = [
    "AssetStatus",
    "AuditAction",
    "BlockType",
    "BuilderType",
    "CampaignStatus",
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
]
