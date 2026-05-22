"""Project WP menu tracking (NAV/FOOTER mapper).

Revision ID: 0019_project_wp_menu
Revises: 0018_asset_upload_tracking
Create Date: 2026-05-22 09:35:00.000000+00:00

Sprint v0.24.0 — Bloque N. El `WpDeployerAgent` crea un WP menu vía
`wp menu create` + `wp menu item add-custom` por cada item extraído
del nav origen. Bricks `nav-menu` espera un `menu` ID numérico apuntando
a un menu pre-existente.

Cambios:
- `projects.nav_items_json` (jsonb): estructura jerárquica
  `[{label, url, target, children: [...]}]` extraída por
  `WixExtractor._extract_nav_items` (también Webflow/Hostinger). El
  agente `wp_deployer` la consume para crear el menu en WP.
- `projects.wp_menu_id` (int): ID numérico del menu creado en el
  destino. Cache para que el resolver del nav-menu element no haga
  query REST extra.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_project_wp_menu"
down_revision: str | None = "0018_asset_upload_tracking"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "nav_items_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "Estructura jerárquica [{label, url, target, children}] "
                "extraída del nav del origen. Consumida por wp_deployer "
                "para crear el WP menu antes del bricks_import_content."
            ),
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "wp_menu_id",
            sa.Integer(),
            nullable=True,
            comment=(
                "ID numérico del WP menu creado en el destino tras "
                "`wp menu create`. Cache para que el nav-menu element "
                "del bricks_json lo referencie sin REST query extra."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "wp_menu_id")
    op.drop_column("projects", "nav_items_json")
