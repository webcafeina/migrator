"""Persistir node_styles y background_image_urls del PlaywrightFetcher.

Revision ID: 0016_node_styles
Revises: 0015_element_styles
Create Date: 2026-05-21 19:50:00.000000+00:00

Sprint v0.23.0 — completa el bloque A: el scraper guarda los computed
styles por nodo individual del origen para que `content_extractor` los
asigne a cada `ContentBlock.element_styles` por matching `node_path`.

Cambios:
- `scraped_pages.node_styles_json` (JSONB): lista de
  `[{node_path, tag, styles}]` capturada por `_CAPTURE_NODE_STYLES_JS`
  en el browser. Volumen estimado ~30-50 KB por página (Wix mariya).
- `scraped_pages.background_image_urls_json` (JSONB): lista de URLs
  cross-origin detectadas en `computed.background-image`. El
  `asset_optimizer` las trata como assets a descargar para R2.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_node_styles"
down_revision: str | None = "0015_element_styles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scraped_pages",
        sa.Column(
            "node_styles_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "Lista [{node_path, tag, styles}] capturada por el JS "
                "_CAPTURE_NODE_STYLES_JS en browser. La consume "
                "content_extractor para asignar element_styles a cada "
                "ContentBlock."
            ),
        ),
    )
    op.add_column(
        "scraped_pages",
        sa.Column(
            "background_image_urls_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "URLs de background-image cross-origin detectadas en "
                "computed styles. asset_optimizer las descarga a R2."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("scraped_pages", "background_image_urls_json")
    op.drop_column("scraped_pages", "node_styles_json")
