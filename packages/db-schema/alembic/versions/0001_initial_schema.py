"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-12

Crea todas las tablas del MVP + extensión pgvector + índice vectorial
para leads.embedding. Escrita manualmente (no autogenerate) para
controlar el orden de creación y los índices especiales (ivfflat).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


LEAD_EMBEDDING_DIM = 1024  # voyage-multilingual-2 (ADR-010). Cambiar requiere re-embedding.


def upgrade() -> None:
    # ---- Extensión pgvector ----
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ---- users ----
    op.create_table(
        "users",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="operator"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_created_at", "users", ["created_at"])

    # ---- leads ----
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("business_name", sa.String(255)),
        sa.Column("sector", sa.String(120)),
        sa.Column("country", sa.String(2), nullable=False, server_default="ES"),
        sa.Column("region", sa.String(120)),
        sa.Column("builder_detected", sa.String(32)),
        sa.Column("builder_confidence", sa.Float),
        sa.Column("builder_evidence", sa.dialects.postgresql.JSONB),
        sa.Column("emails", sa.dialects.postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("phones", sa.dialects.postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("social_links", sa.dialects.postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="discovered"),
        sa.Column("score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_crawl_at", sa.DateTime(timezone=True)),
        sa.Column("embedding", Vector(LEAD_EMBEDDING_DIM)),
        sa.Column("embedding_model", sa.String(80)),
        sa.Column("embedding_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("url", name="uq_leads_url"),
    )
    op.create_index("ix_leads_url", "leads", ["url"])
    op.create_index("ix_leads_sector", "leads", ["sector"])
    op.create_index("ix_leads_region", "leads", ["region"])
    op.create_index("ix_leads_builder_detected", "leads", ["builder_detected"])
    op.create_index("ix_leads_status", "leads", ["status"])
    op.create_index("ix_leads_score", "leads", ["score"])
    op.create_index("ix_leads_created_at", "leads", ["created_at"])
    # Índice vectorial: ivfflat con cosine distance. lists=100 es razonable
    # hasta ~1M filas; revisar a partir de ahí.
    op.execute(
        "CREATE INDEX ix_leads_embedding ON leads "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    # ---- lead_enrichments ----
    op.create_table(
        "lead_enrichments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("lead_id", sa.Integer, sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("employees_estimate", sa.Integer),
        sa.Column("revenue_estimate_eur", sa.Integer),
        sa.Column("tech_stack", sa.dialects.postgresql.ARRAY(sa.String)),
        sa.Column("traffic_estimate_monthly", sa.Integer),
        sa.Column("ahrefs_dr", sa.Float),
        sa.Column("legal_ground", sa.String(40)),
        sa.Column("raw_payload", sa.dialects.postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_lead_enrichments_lead_id", "lead_enrichments", ["lead_id"])
    op.create_index("ix_lead_enrichments_created_at", "lead_enrichments", ["created_at"])

    # ---- opt_out_log ----
    op.create_table(
        "opt_out_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("lead_id_at_optout", sa.Integer),
        sa.Column("channel", sa.String(40), nullable=False, server_default="email"),
        sa.Column("evidence", sa.Text),
        sa.Column("opted_out_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", "channel", name="uq_opt_out_log_email_channel"),
    )
    op.create_index("ix_opt_out_log_email", "opt_out_log", ["email"])

    # ---- outreach_sequences ----
    op.create_table(
        "outreach_sequences",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("lead_id", sa.Integer, sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_name", sa.String(80), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False, server_default="email"),
        sa.Column("steps_json", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft_pending_review"),
        sa.Column("legal_validation_passed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("legal_validator_version", sa.String(16)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_outreach_sequences_lead_id", "outreach_sequences", ["lead_id"])
    op.create_index("ix_outreach_sequences_status", "outreach_sequences", ["status"])
    op.create_index("ix_outreach_sequences_created_at", "outreach_sequences", ["created_at"])

    # ---- outreach_sends ----
    op.create_table(
        "outreach_sends",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "sequence_id",
            sa.Integer,
            sa.ForeignKey("outreach_sequences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("lead_id", sa.Integer, sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_index", sa.Integer, nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("subject", sa.String(255)),
        sa.Column("body_rendered", sa.Text),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("opened_at", sa.DateTime(timezone=True)),
        sa.Column("replied_at", sa.DateTime(timezone=True)),
        sa.Column("bounced_at", sa.DateTime(timezone=True)),
        sa.Column("provider_message_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("sequence_id", "step_index", name="uq_outreach_sends_sequence_step"),
    )
    op.create_index("ix_outreach_sends_sequence_id", "outreach_sends", ["sequence_id"])
    op.create_index("ix_outreach_sends_lead_id", "outreach_sends", ["lead_id"])
    op.create_index("ix_outreach_sends_status", "outreach_sends", ["status"])
    op.create_index("ix_outreach_sends_created_at", "outreach_sends", ["created_at"])

    # ---- projects ----
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("lead_id", sa.Integer, sa.ForeignKey("leads.id", ondelete="SET NULL")),
        sa.Column("client_name", sa.String(255), nullable=False),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("target_domain", sa.String(255)),
        sa.Column("builder_source", sa.String(32)),
        sa.Column("has_ecommerce", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_multilang", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("langs", sa.dialects.postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("primary_lang", sa.String(8)),
        sa.Column("asset_storage", sa.String(16), nullable=False, server_default="wp_local"),
        sa.Column("preserve_paths", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("hosting_target_json", sa.dialects.postgresql.JSONB),
        sa.Column("theme_styles_origin", sa.dialects.postgresql.JSONB),
        sa.Column("visual_diff_ignore", sa.dialects.postgresql.JSONB),
        sa.Column("visual_diff_avg_score", sa.Float),
        sa.Column("deploy_credentials_encrypted", sa.Text),
        sa.Column("plan", sa.String(40)),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("estimated_go_live_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_projects_lead_id", "projects", ["lead_id"])
    op.create_index("ix_projects_target_domain", "projects", ["target_domain"])
    op.create_index("ix_projects_status", "projects", ["status"])
    op.create_index("ix_projects_created_at", "projects", ["created_at"])

    # ---- project_phases ----
    op.create_table(
        "project_phases",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer,
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phase_name", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_log", sa.Text),
        sa.Column("output_summary", sa.dialects.postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "phase_name", name="uq_project_phases_project_phase"),
    )
    op.create_index("ix_project_phases_project_id", "project_phases", ["project_id"])
    op.create_index("ix_project_phases_status", "project_phases", ["status"])
    op.create_index("ix_project_phases_created_at", "project_phases", ["created_at"])

    # ---- scraped_pages ----
    op.create_table(
        "scraped_pages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer,
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("slug", sa.String(255)),
        sa.Column("title", sa.String(512)),
        sa.Column("lang", sa.String(8)),
        sa.Column("depth", sa.Integer, nullable=False, server_default="0"),
        sa.Column("html_raw", sa.Text),
        sa.Column("html_clean", sa.Text),
        sa.Column("screenshot_path", sa.String(1024)),
        sa.Column("screenshot_mobile_path", sa.String(1024)),
        sa.Column("dom_tree_json", sa.dialects.postgresql.JSONB),
        sa.Column("css_extracted", sa.Text),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("scraped_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "url", name="uq_scraped_pages_project_url"),
    )
    op.create_index("ix_scraped_pages_project_id", "scraped_pages", ["project_id"])
    op.create_index("ix_scraped_pages_slug", "scraped_pages", ["slug"])
    op.create_index("ix_scraped_pages_lang", "scraped_pages", ["lang"])
    op.create_index("ix_scraped_pages_status", "scraped_pages", ["status"])
    op.create_index("ix_scraped_pages_created_at", "scraped_pages", ["created_at"])

    # ---- assets ----
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer,
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("original_url", sa.String(2048), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.Column("mime", sa.String(80)),
        sa.Column("size_bytes", sa.Integer),
        sa.Column("width", sa.Integer),
        sa.Column("height", sa.Integer),
        sa.Column("local_path", sa.String(1024)),
        sa.Column("optimized_path", sa.String(1024)),
        sa.Column("r2_key", sa.String(1024)),
        sa.Column("wp_attachment_id", sa.Integer),
        sa.Column("alt_text", sa.Text),
        sa.Column("sizes_json", sa.dialects.postgresql.JSONB),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "hash", name="uq_assets_project_hash"),
    )
    op.create_index("ix_assets_project_id", "assets", ["project_id"])
    op.create_index("ix_assets_hash", "assets", ["hash"])
    op.create_index("ix_assets_status", "assets", ["status"])
    op.create_index("ix_assets_created_at", "assets", ["created_at"])

    # ---- content_blocks ----
    op.create_table(
        "content_blocks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer,
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "page_id",
            sa.Integer,
            sa.ForeignKey("scraped_pages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("block_type", sa.String(32), nullable=False),
        sa.Column("order_index", sa.Integer, nullable=False),
        sa.Column("lang", sa.String(8)),
        sa.Column("content_json", sa.dialects.postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("source", sa.String(16), nullable=False, server_default="extracted"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_content_blocks_project_id", "content_blocks", ["project_id"])
    op.create_index("ix_content_blocks_page_id", "content_blocks", ["page_id"])
    op.create_index("ix_content_blocks_block_type", "content_blocks", ["block_type"])
    op.create_index("ix_content_blocks_lang", "content_blocks", ["lang"])
    op.create_index("ix_content_blocks_created_at", "content_blocks", ["created_at"])

    # ---- bricks_pages ----
    op.create_table(
        "bricks_pages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer,
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_id", sa.Integer, sa.ForeignKey("scraped_pages.id", ondelete="SET NULL")),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("lang", sa.String(8)),
        sa.Column("bricks_json", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("bricks_schema_version", sa.String(16)),
        sa.Column("seo_meta", sa.dialects.postgresql.JSONB),
        sa.Column("wp_post_id", sa.Integer),
        sa.Column("wpml_trid", sa.Integer),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("last_import_error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "slug", "lang", name="uq_bricks_pages_project_slug_lang"),
    )
    op.create_index("ix_bricks_pages_project_id", "bricks_pages", ["project_id"])
    op.create_index("ix_bricks_pages_page_id", "bricks_pages", ["page_id"])
    op.create_index("ix_bricks_pages_wp_post_id", "bricks_pages", ["wp_post_id"])
    op.create_index("ix_bricks_pages_wpml_trid", "bricks_pages", ["wpml_trid"])
    op.create_index("ix_bricks_pages_status", "bricks_pages", ["status"])
    op.create_index("ix_bricks_pages_created_at", "bricks_pages", ["created_at"])

    # ---- woo_products ----
    op.create_table(
        "woo_products",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer,
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_id", sa.String(80)),
        sa.Column("sku", sa.String(80), nullable=False),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("price", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("stock", sa.Integer),
        sa.Column("stock_managed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("attributes_json", sa.dialects.postgresql.JSONB),
        sa.Column("variations_json", sa.dialects.postgresql.JSONB),
        sa.Column(
            "image_asset_ids",
            sa.dialects.postgresql.ARRAY(sa.Integer),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("categories", sa.dialects.postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("wp_product_id", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "sku", name="uq_woo_products_project_sku"),
    )
    op.create_index("ix_woo_products_project_id", "woo_products", ["project_id"])
    op.create_index("ix_woo_products_wp_product_id", "woo_products", ["wp_product_id"])
    op.create_index("ix_woo_products_created_at", "woo_products", ["created_at"])

    # ---- seo_redirects ----
    op.create_table(
        "seo_redirects",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer,
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_path", sa.String(2048), nullable=False),
        sa.Column("target_path", sa.String(2048), nullable=False),
        sa.Column("http_status", sa.Integer, nullable=False, server_default="301"),
        sa.Column("wp_redirect_id", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "source_path", name="uq_seo_redirects_project_source"),
    )
    op.create_index("ix_seo_redirects_project_id", "seo_redirects", ["project_id"])
    op.create_index("ix_seo_redirects_created_at", "seo_redirects", ["created_at"])

    # ---- residual_tasks ----
    op.create_table(
        "residual_tasks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer,
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("estimated_minutes", sa.Integer),
        sa.Column(
            "screenshot_paths",
            sa.dialects.postgresql.ARRAY(sa.String),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("generated_by", sa.String(64)),
        sa.Column("clickup_task_id", sa.String(40)),
        sa.Column("assignee_hint", sa.String(64)),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_residual_tasks_project_id", "residual_tasks", ["project_id"])
    op.create_index("ix_residual_tasks_category", "residual_tasks", ["category"])
    op.create_index("ix_residual_tasks_status", "residual_tasks", ["status"])
    op.create_index("ix_residual_tasks_clickup_task_id", "residual_tasks", ["clickup_task_id"])
    op.create_index("ix_residual_tasks_created_at", "residual_tasks", ["created_at"])

    # ---- audit_log ----
    op.create_table(
        "audit_log",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("entity_type", sa.String(64)),
        sa.Column("entity_id", sa.String(64)),
        sa.Column("payload", sa.dialects.postgresql.JSONB),
        sa.Column("legal_ground", sa.String(40)),
    )
    op.create_index("ix_audit_log_at", "audit_log", ["at"])
    op.create_index("ix_audit_log_actor", "audit_log", ["actor"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_entity_type", "audit_log", ["entity_type"])
    op.create_index("ix_audit_log_entity_id", "audit_log", ["entity_id"])

    # ---- error_log ----
    op.create_table(
        "error_log",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("project_id", sa.Integer),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("component", sa.String(64), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("stack", sa.Text),
        sa.Column("context_json", sa.dialects.postgresql.JSONB),
        sa.Column("sentry_event_id", sa.String(40)),
        sa.Column("notified_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_error_log_at", "error_log", ["at"])
    op.create_index("ix_error_log_project_id", "error_log", ["project_id"])
    op.create_index("ix_error_log_severity", "error_log", ["severity"])
    op.create_index("ix_error_log_component", "error_log", ["component"])


def downgrade() -> None:
    op.drop_table("error_log")
    op.drop_table("audit_log")
    op.drop_table("residual_tasks")
    op.drop_table("seo_redirects")
    op.drop_table("woo_products")
    op.drop_table("bricks_pages")
    op.drop_table("content_blocks")
    op.drop_table("assets")
    op.drop_table("scraped_pages")
    op.drop_table("project_phases")
    op.drop_table("projects")
    op.drop_table("outreach_sends")
    op.drop_table("outreach_sequences")
    op.drop_table("opt_out_log")
    op.drop_table("lead_enrichments")
    # El índice ix_leads_embedding se borra junto con la tabla
    op.drop_table("leads")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
