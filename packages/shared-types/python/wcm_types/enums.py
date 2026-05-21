"""Enums compartidos por todo el dominio.

Fuente única de la verdad. SQLAlchemy los re-importa; pydantic2ts los
detecta y genera los `enum` TS equivalentes.

Decisión: usar StrEnum para que los valores sean strings legibles tanto
en la BD (columna VARCHAR) como en el cliente TS (igual literal).
"""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class LeadStatus(StrEnum):
    DISCOVERED = "discovered"
    FINGERPRINTED = "fingerprinted"
    ENRICHED = "enriched"
    OUTREACH_PREPARED = "outreach_prepared"
    OUTREACH_SENT = "outreach_sent"
    RESPONDED = "responded"
    CONVERTED = "converted"
    MANUAL_REVIEW = "manual_review"
    OPTED_OUT = "opted_out"
    DISCARDED = "discarded"


class BuilderType(StrEnum):
    WIX = "wix"
    HOSTINGER_AI = "hostinger_ai"
    WEBFLOW = "webflow"
    WORDPRESS = "wordpress"
    SQUARESPACE = "squarespace"
    SHOPIFY = "shopify"
    OTHER = "other"
    UNKNOWN = "unknown"


class OutreachChannel(StrEnum):
    EMAIL = "email"
    LINKEDIN = "linkedin"
    FORM = "form"


class OutreachSequenceStatus(StrEnum):
    DRAFT_PENDING_REVIEW = "draft_pending_review"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PAUSED = "paused"
    OPTED_OUT = "opted_out"


class OutreachSendStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    BOUNCED = "bounced"
    OPENED = "opened"
    REPLIED = "replied"
    FAILED = "failed"


class ProjectStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    BLOCKED_HUMAN_INPUT = "blocked_human_input"
    QA_FAILED = "qa_failed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    #: v0.19.0 — operador ejecutó rollback tras qa_failed/completed.
    #: Las páginas creadas por wp-deployer fueron eliminadas vía REST.
    ROLLED_BACK = "rolled_back"


class ProjectPhaseStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ScrapeStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class CampaignStatus(StrEnum):
    QUEUED = "queued"  # encolada, worker aún no la ha cogido
    RUNNING = "running"  # prospector + chain enrich corriendo
    COMPLETED = "completed"  # todos los leads pasaron por enrich (o 0 leads)
    FAILED = "failed"  # error definitivo
    CANCELLED = "cancelled"  # operador la canceló manualmente


class AssetStatus(StrEnum):
    PENDING = "pending"
    DOWNLOADED = "downloaded"
    OPTIMIZED = "optimized"
    UPLOADED = "uploaded"
    READY = "ready"
    MISSING = "missing"
    FAILED = "failed"


class BlockType(StrEnum):
    HERO = "hero"
    TEXT = "text"
    HEADING = "heading"
    IMAGE = "image"
    GALLERY = "gallery"
    CTA = "cta"
    FORM = "form"
    TESTIMONIAL = "testimonial"
    PRICING = "pricing"
    FAQ = "faq"
    PRODUCT_CARD = "product_card"
    VIDEO = "video"
    EMBED = "embed"
    DIVIDER = "divider"
    NAV = "nav"
    FOOTER = "footer"
    #: Grid/lista de items (cards repetidas con img+heading+link). Caso
    #: típico: `wixui-repeater` con N case-studies o servicios. B.4 (2026-05-20).
    GRID = "grid"
    #: Sprint v0.22.0 — bloque cuyos elementos Bricks fueron generados
    #: por Claude Vision (AiAssistAgent). El content_json contiene
    #: `bricks_elements: list[BricksElement-shaped dict]` que el mapper
    #: emite tal cual.
    AI_GENERATED = "ai_generated"
    #: Sprint v0.22.0 — fallback cuando ni heurística ni AI pueden
    #: reproducir la sección con elementos nativos. content_json contiene
    #: `html: str` y `css: str` del origen. El mapper emite un único
    #: elemento Bricks `code` con namespace CSS.
    RAW_HTML = "raw_html"
    UNKNOWN = "unknown"


class ContentBlockSource(StrEnum):
    EXTRACTED = "extracted"
    EDITED = "edited"
    INSERTED = "inserted"


class ResidualCategory(StrEnum):
    BLOCKING_GO_LIVE = "blocking_go_live"
    CLIENT_CONFIG = "client_config"
    VISUAL_CONTENT = "visual_content"
    POST_GO_LIVE = "post_go_live"
    OTHER = "other"


class ResidualStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    SKIPPED = "skipped"


class AuditAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    DISCOVER = "discover"
    FINGERPRINT = "fingerprint"
    ENRICH = "enrich"
    SEND = "send"
    # v0.14.0 — envío de prueba a una dirección arbitraria desde la UI
    # del editor de pasos. NO crea OutreachSend ni muta el sequence;
    # solo registra en audit-log para trazabilidad (qué operador probó
    # qué step contra qué email). Separado de SEND para no contaminar
    # métricas de outreach real.
    TEST_SEND = "test_send"
    OPT_OUT = "opt_out"
    DEPLOY = "deploy"
    QA = "qa"
    SYSTEM = "system"
    # v0.14.0 — edición de la shell HTML maestra desde
    # /settings/email-layout. Capa de auditoría adicional al
    # `updated_by_user_id` que también persiste en la tabla.
    EMAIL_LAYOUT_UPDATE = "email_layout_update"


class ErrorSeverity(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
