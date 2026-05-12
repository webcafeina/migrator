"""Los enums viven en wcm_types y se re-exportan desde wcm_db.enums.
Aquí validamos que ambos paquetes ven exactamente los mismos miembros.
"""

from __future__ import annotations

import wcm_db.enums as db_enums
import wcm_types.enums as types_enums


ENUM_NAMES = [
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
]


def test_db_reexports_same_enum_objects() -> None:
    """wcm_db.enums.* debe ser EL MISMO objeto que wcm_types.enums.* (is)."""
    for name in ENUM_NAMES:
        db_cls = getattr(db_enums, name)
        types_cls = getattr(types_enums, name)
        assert db_cls is types_cls, f"Enum desincronizado: {name}"


def test_known_enum_members_present() -> None:
    """Sanity check de algunos miembros críticos."""
    assert types_enums.LeadStatus.OPTED_OUT.value == "opted_out"
    assert types_enums.BuilderType.WIX.value == "wix"
    assert types_enums.ProjectStatus.QA_FAILED.value == "qa_failed"
    assert types_enums.ResidualCategory.BLOCKING_GO_LIVE.value == "blocking_go_live"
