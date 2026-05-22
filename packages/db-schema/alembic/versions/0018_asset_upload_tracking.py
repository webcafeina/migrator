"""Asset upload tracking (R2→WP media library).

Revision ID: 0018_asset_upload_tracking
Revises: 0017_global_classes
Create Date: 2026-05-22 09:30:00.000000+00:00

Sprint v0.24.0 — Bloque A. El nuevo `AssetUploaderAgent` necesita
saber si un asset ya está en la WP media library del destino para
ser idempotente (re-run safe).

Cambios:
- `assets.wp_media_uploaded_at` (timestamp): cuándo se subió a WP.
  Idempotencia: si NOT NULL → skip upload, el wp_attachment_id ya
  refleja la realidad del destino.
- `assets.wp_source_url` (varchar): URL canónica del attachment en
  el destino (`<wp>/wp-content/uploads/2026/05/imagen.webp`). Cache
  para que el agente no haga GET extra al reescribir URLs en
  bricks_json. Si wp_attachment_id existe pero wp_source_url es NULL
  → fallback consultar REST `/wp/v2/media/{id}`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_asset_upload_tracking"
down_revision: str | None = "0017_global_classes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "assets",
        sa.Column(
            "wp_media_uploaded_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                "Timestamp del upload exitoso a WP media library. NULL = "
                "pending. Idempotencia AssetUploaderAgent."
            ),
        ),
    )
    op.add_column(
        "assets",
        sa.Column(
            "wp_source_url",
            sa.String(length=2048),
            nullable=True,
            comment=(
                "URL canónica del attachment en el WP destino "
                "(<wp>/wp-content/uploads/YYYY/MM/file.ext). Cache para "
                "reescritura masiva de bricks_json sin GET REST por asset."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("assets", "wp_source_url")
    op.drop_column("assets", "wp_media_uploaded_at")
