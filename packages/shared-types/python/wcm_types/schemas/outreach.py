from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AliasChoices, ConfigDict, EmailStr, Field

from wcm_types.enums import OutreachChannel, OutreachSendStatus, OutreachSequenceStatus
from wcm_types.schemas._base import TimestampedRead, WcmModel


class OutreachTemplateBase(WcmModel):
    """Plantilla Jinja2 reutilizable usada por el composer al generar
    drafts. v0.12.0 — migrada de fichero `.j2` a tabla BD editable.
    v0.14.0 — añadidos `body_html_template` (HTML opcional) y CTA."""

    name: str = Field(min_length=1, max_length=80)
    subject_template: str = Field(min_length=1)
    body_template: str = Field(min_length=1)
    language: str = Field(default="es", min_length=2, max_length=8)
    # v0.14.0 — opcional. Si NULL, composer cae a `body_template` texto
    # y lo envuelve en `<p>` automáticamente al renderizar.
    body_html_template: str | None = Field(default=None)
    # CTA opcional pintado por el layout si ambos están rellenos.
    cta_label: str | None = Field(default=None, max_length=80)
    cta_url: str | None = Field(default=None, max_length=500)


class OutreachTemplateCreate(OutreachTemplateBase):
    """Crear plantilla nueva. `name` debe ser único."""


class OutreachTemplateUpdate(WcmModel):
    """Actualizar plantilla existente. Todos los campos opcionales —
    `name` NO se cambia (es la clave por la que el composer la
    resuelve; renombrar rompería sequences históricas que la
    referencian)."""

    subject_template: str | None = Field(default=None, min_length=1)
    body_template: str | None = Field(default=None, min_length=1)
    language: str | None = Field(default=None, min_length=2, max_length=8)
    # v0.14.0. `None` significa "no tocar"; string vacío "" significa
    # "vaciar" (volver a fallback texto). Distinción gestionada en el
    # router con `model_dump(exclude_unset=True)`.
    body_html_template: str | None = Field(default=None)
    cta_label: str | None = Field(default=None, max_length=80)
    cta_url: str | None = Field(default=None, max_length=500)


class OutreachTemplateRead(OutreachTemplateBase, TimestampedRead):
    id: int


class OutreachStepEdit(WcmModel):
    """Payload para editar un paso desde la UI. NO se permite cambiar
    step_index (preserva orden del template original); add/delete steps
    se hace re-componiendo el draft, no editando."""

    step_index: int = Field(ge=0)
    subject: str | None = Field(default=None, max_length=255)
    body: str = Field(min_length=1)
    delay_days_from_previous: int = Field(default=0, ge=0)


class OutreachStepsUpdatePayload(WcmModel):
    """PATCH /sequences/{id}/steps. La lista debe contener TODOS los
    steps de la sequence (semántica de reemplazo, no patch parcial)
    para que la validación legal se corra sobre el resultado completo."""

    steps: list[OutreachStepEdit] = Field(min_length=1, max_length=10)


class OutreachStep(WcmModel):
    """Un paso dentro de steps_json — validado para asegurar mínimos LSSI-CE.

    Tolerante con shapes legacy (fix v0.11.1): sequences viejas
    persistidas en BD tienen `delay_days` (sin `_from_previous`) y
    pueden traer campos extra (`template`). Para no romper su lectura
    desde el dashboard:

    - `step_index` opcional con default 0 (se infiere del orden si falta).
    - `delay_days_from_previous` acepta también el alias `delay_days`
      vía `AliasChoices`.
    - `extra="allow"` permite cualquier campo adicional sin lanzar 500.
      Los composers nuevos siguen escribiendo solo el shape canónico.
    """

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        extra="allow",  # tolerancia a sequences legacy en BD
        populate_by_name=True,
    )

    step_index: int = Field(default=0, ge=0)
    subject: str | None = Field(default=None, max_length=255)
    body: str
    delay_days_from_previous: int = Field(
        default=0,
        ge=0,
        validation_alias=AliasChoices("delay_days_from_previous", "delay_days"),
    )
    legal_footer_included: bool = True


class OutreachSequenceBase(WcmModel):
    template_name: str = Field(max_length=80)
    name: str = Field(max_length=255)
    channel: OutreachChannel = OutreachChannel.EMAIL
    steps_json: list[OutreachStep]


class OutreachSequenceCreate(OutreachSequenceBase):
    lead_id: int


class OutreachSequenceRead(OutreachSequenceBase, TimestampedRead):
    id: int
    lead_id: int
    status: OutreachSequenceStatus
    legal_validation_passed: bool
    legal_validator_version: str | None


class OutreachSendRead(WcmModel):
    id: int
    sequence_id: int
    lead_id: int
    step_index: int
    channel: OutreachChannel
    subject: str | None
    body_rendered: str | None
    # v0.14.0 — snapshot HTML del envío. NULL para sends históricos
    # pre-v0.14.0; la UI muestra el text en su lugar.
    body_html_rendered: str | None = None
    status: OutreachSendStatus
    sent_at: datetime | None
    opened_at: datetime | None
    replied_at: datetime | None
    bounced_at: datetime | None
    provider_message_id: str | None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


# --- v0.14.0: Email layout singleton + preview + test-send ---


HEX_COLOR_PATTERN = r"^#[0-9A-Fa-f]{6}$"


class EmailLayoutTheme(WcmModel):
    """Configuración del tema visual del layout maestro (v0.15.0).

    Cuando el operador edita desde el tab "Visual" de `/settings/email-layout`,
    este JSON se persiste en `email_layouts.theme_config` y el backend
    regenera `layout_html` + `layout_css` desde la plantilla canónica
    de Webcafeína usando estos valores.

    Todos los campos tienen defaults que coinciden con la marca
    Webcafeína (acento lima `#B1F100` sobre fondo claro, system-ui).
    El form los puede sobrescribir todos.

    Validaciones:
    - Colores: HEX 6 chars (`#RRGGBB`).
    - Dimensiones: bounds razonables para email (ancho 320-720, padding 0-64,
      radius 0-12). Valores fuera de rango → 422.
    - Tipografía: literal limitado a opciones email-safe.
    """

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        # Ignora claves desconocidas en JSONs antiguos (forward-compat
        # cuando añadamos campos nuevos en futuras versiones del tema).
        extra="ignore",
        populate_by_name=True,
    )

    # --- Colores principales ---
    cta_bg: str = Field(default="#B1F100", pattern=HEX_COLOR_PATTERN)
    cta_text: str = Field(default="#0E1218", pattern=HEX_COLOR_PATTERN)
    cta_border: str = Field(default="#94C800", pattern=HEX_COLOR_PATTERN)
    page_bg: str = Field(default="#F5F6F8", pattern=HEX_COLOR_PATTERN)
    card_bg: str = Field(default="#FFFFFF", pattern=HEX_COLOR_PATTERN)
    card_border: str = Field(default="#E5E7EB", pattern=HEX_COLOR_PATTERN)
    text_color: str = Field(default="#1F2937", pattern=HEX_COLOR_PATTERN)
    text_strong: str = Field(default="#0E1218", pattern=HEX_COLOR_PATTERN)
    link_color: str = Field(default="#5A8A00", pattern=HEX_COLOR_PATTERN)
    footer_text: str = Field(default="#6B7280", pattern=HEX_COLOR_PATTERN)
    brand_accent: str = Field(
        default="#5A8A00",
        pattern=HEX_COLOR_PATTERN,
        description="Color del acento de marca ('í' de webcafeína cuando se usa texto en lugar de logo).",
    )

    # --- Branding ---
    show_logo: bool = Field(default=True)
    logo_url_override: str | None = Field(
        default=None,
        max_length=500,
        description="URL alternativa para el logo de este tema. Si None, usa EMAIL_LOGO_URL del env.",
    )
    logo_max_width_px: int = Field(default=160, ge=80, le=400)

    # --- Tipografía ---
    font_family: Literal["system-ui", "serif", "Inter"] = Field(default="system-ui")
    body_font_size_px: int = Field(default=15, ge=12, le=20)
    body_line_height: float = Field(default=1.65, ge=1.2, le=2.2)
    brand_text_size_px: int = Field(default=22, ge=14, le=32)

    # --- Espaciado y dimensiones ---
    card_max_width_px: int = Field(default=600, ge=320, le=720)
    content_padding_px: int = Field(default=28, ge=8, le=64)
    header_padding_px: int = Field(default=28, ge=8, le=64)
    footer_padding_px: int = Field(default=18, ge=8, le=64)

    # --- Bordes y radius ---
    card_border_radius_px: int = Field(default=6, ge=0, le=12)
    cta_border_radius_px: int = Field(default=4, ge=0, le=12)
    card_border_width_px: int = Field(default=1, ge=0, le=4)


def default_theme() -> EmailLayoutTheme:
    """Construye un EmailLayoutTheme con todos los defaults Webcafeína.

    Atajo para los endpoints "reset" y para el seed inicial del tema
    en la migración 0006.
    """
    return EmailLayoutTheme()


class EmailLayoutRead(TimestampedRead):
    """Lectura del singleton `email_layouts` (id=1).

    Cualquier admin puede leerlo. La UI de `/settings/email-layout` lo
    usa para hidratar el editor inicial.
    """

    id: int
    layout_html: str
    layout_css: str
    # v0.15.0 — si NULL, el layout fue editado a código manualmente.
    # Si poblado, el frontend puede ofrecer edición visual.
    theme_config: EmailLayoutTheme | None = None
    updated_by_user_id: UUID | None = None


class EmailLayoutUpdate(WcmModel):
    """PUT /email-layout. v0.15.0 ahora acepta 3 modos:

    1. Solo `theme_config` → backend regenera `layout_html` y `layout_css`
       desde la plantilla canónica.
    2. Solo `layout_html` + `layout_css` → backend persiste tal cual y
       borra `theme_config` (modo Código avanzado).
    3. Los 3 campos → respeta `theme_config` y usa el HTML/CSS que
       acompañe (útil si el frontend ya regeneró client-side por consistencia).

    Validaciones mínimas: si llega `layout_html` debe tener min 1 char
    (no se permite vaciar el layout completamente).
    """

    layout_html: str | None = Field(default=None, min_length=1)
    layout_css: str | None = Field(default=None)
    theme_config: EmailLayoutTheme | None = Field(default=None)
    # Marcador explícito: si True, el cliente quiere borrar el tema y
    # dejar `theme_config=NULL` (modo Código). Útil para distinguir
    # "no se mandó" de "se quiere borrar".
    clear_theme: bool = Field(default=False)


class OutreachPreviewResponse(WcmModel):
    """Respuesta de los endpoints preview (template y step).

    El `html` ya viene con CSS inlined por premailer — listo para
    pintar en un iframe `srcDoc`. El `subject` lo retornamos solo en
    el preview de plantilla (con contexto mockeado); en preview de
    step ya hay subject persistido y la UI lo conoce, pero lo
    incluimos también para consistencia.
    """

    html: str
    subject: str | None = None


class OutreachTestSendPayload(WcmModel):
    """POST /outreach/sequences/{id}/steps/{idx}/test-send.

    El operador escribe libremente el destino (puede ser su email
    personal, otro Webcafeínero, etc.) para verificar visualmente que
    el correo llega bien antes de aprobar el envío real al lead.
    """

    to: EmailStr


class OutreachTestSendResponse(WcmModel):
    """Resultado del envío de prueba."""

    provider_message_id: str | None
    to: EmailStr
