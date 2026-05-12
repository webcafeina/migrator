// AUTO-GENERATED FILE. DO NOT EDIT MANUALLY.
// Source: packages/shared-types/python/wcm_types/
// Regenerate with: pnpm gen:types  (or bash scripts/gen-ts.sh)
// Generated at: 2026-05-12T12:12:19Z

/* tslint:disable */
/* eslint-disable */
/**
/* This file was automatically generated from pydantic models by running pydantic2ts.
/* Do not modify it by hand - just update the pydantic models and then re-run the script
*/

export type AssetStatus = "pending" | "downloaded" | "optimized" | "uploaded" | "ready" | "missing" | "failed";
export type AuditAction =
  | "create"
  | "update"
  | "delete"
  | "discover"
  | "fingerprint"
  | "enrich"
  | "send"
  | "opt_out"
  | "deploy"
  | "qa"
  | "system";
export type ScrapeStatus = "pending" | "success" | "failed" | "skipped";
export type BlockType =
  | "hero"
  | "text"
  | "heading"
  | "image"
  | "gallery"
  | "cta"
  | "form"
  | "testimonial"
  | "pricing"
  | "faq"
  | "product_card"
  | "video"
  | "embed"
  | "divider"
  | "nav"
  | "footer"
  | "unknown";
export type ContentBlockSource = "extracted" | "edited" | "inserted";
export type ContentBlockSource1 = "extracted" | "edited" | "inserted";
export type ErrorSeverity = "debug" | "info" | "warning" | "error" | "critical";
export type BuilderType =
  | "wix"
  | "hostinger_ai"
  | "webflow"
  | "wordpress"
  | "squarespace"
  | "shopify"
  | "other"
  | "unknown";
export type LeadStatus =
  | "discovered"
  | "fingerprinted"
  | "enriched"
  | "outreach_prepared"
  | "outreach_sent"
  | "responded"
  | "converted"
  | "manual_review"
  | "opted_out"
  | "discarded";
export type OutreachChannel = "email" | "linkedin" | "form";
export type OutreachSendStatus = "queued" | "sent" | "bounced" | "opened" | "replied" | "failed";
export type OutreachChannel1 = "email" | "linkedin" | "form";
export type OutreachChannel2 = "email" | "linkedin" | "form";
export type OutreachSequenceStatus =
  | "draft_pending_review"
  | "ready"
  | "in_progress"
  | "completed"
  | "paused"
  | "opted_out";
export type ProjectPhaseStatus = "pending" | "running" | "completed" | "failed" | "skipped";
export type ProjectStatus = "queued" | "running" | "blocked_human_input" | "qa_failed" | "completed" | "cancelled";
export type ResidualCategory = "blocking_go_live" | "client_config" | "visual_content" | "post_go_live" | "other";
export type ResidualStatus = "open" | "in_progress" | "blocked" | "done" | "skipped";
export type UserRole = "admin" | "operator" | "viewer";
export type UserRole1 = "admin" | "operator" | "viewer";
export type ContentBlockSource2 = "extracted" | "edited" | "inserted";
export type OutreachChannel3 = "email" | "linkedin" | "form";
export type UserRole2 = "admin" | "operator" | "viewer";

export interface AssetCreate {
  original_url: string;
  hash: string;
  mime?: string | null;
  size_bytes?: number | null;
  width?: number | null;
  height?: number | null;
  alt_text?: string | null;
  project_id: number;
}
export interface AssetRead {
  created_at: string;
  updated_at: string;
  original_url: string;
  hash: string;
  mime?: string | null;
  size_bytes?: number | null;
  width?: number | null;
  height?: number | null;
  alt_text?: string | null;
  id: number;
  project_id: number;
  local_path: string | null;
  optimized_path: string | null;
  r2_key: string | null;
  wp_attachment_id: number | null;
  sizes_json: {
    [k: string]: unknown;
  } | null;
  status: AssetStatus;
  error_message: string | null;
}
export interface AuditLogRead {
  id: string;
  at: string;
  actor: string;
  action: AuditAction;
  entity_type: string | null;
  entity_id: string | null;
  payload: {
    [k: string]: unknown;
  } | null;
  legal_ground: string | null;
}
export interface BricksPageRead {
  created_at: string;
  updated_at: string;
  id: number;
  project_id: number;
  page_id: number | null;
  slug: string;
  title: string;
  lang?: string | null;
  bricks_schema_version: string | null;
  seo_meta: {
    [k: string]: unknown;
  } | null;
  wp_post_id: number | null;
  wpml_trid: number | null;
  status: ScrapeStatus;
  last_import_error: string | null;
}
export interface ContentBlockCreate {
  block_type: BlockType;
  order_index: number;
  lang?: string | null;
  content_json?: {
    [k: string]: unknown;
  };
  source?: ContentBlockSource;
  project_id: number;
  page_id: number;
}
export interface ContentBlockRead {
  created_at: string;
  updated_at: string;
  block_type: BlockType;
  order_index: number;
  lang?: string | null;
  content_json?: {
    [k: string]: unknown;
  };
  source?: ContentBlockSource1;
  id: number;
  project_id: number;
  page_id: number;
}
export interface ErrorLogRead {
  id: string;
  at: string;
  project_id: number | null;
  severity: ErrorSeverity;
  component: string;
  message: string;
  stack: string | null;
  context_json: {
    [k: string]: unknown;
  } | null;
  sentry_event_id: string | null;
  notified_at: string | null;
}
/**
 * Payload de descubrimiento — solo campos derivables sin enrichment.
 */
export interface LeadCreate {
  url: string;
  business_name?: string | null;
  sector?: string | null;
  country?: string;
  region?: string | null;
}
export interface LeadEnrichmentCreate {
  source: string;
  employees_estimate?: number | null;
  revenue_estimate_eur?: number | null;
  tech_stack?: string[] | null;
  traffic_estimate_monthly?: number | null;
  ahrefs_dr?: number | null;
  legal_ground?: string | null;
  raw_payload?: {
    [k: string]: unknown;
  } | null;
  lead_id: number;
}
export interface LeadEnrichmentRead {
  created_at: string;
  updated_at: string;
  source: string;
  employees_estimate?: number | null;
  revenue_estimate_eur?: number | null;
  tech_stack?: string[] | null;
  traffic_estimate_monthly?: number | null;
  ahrefs_dr?: number | null;
  legal_ground?: string | null;
  raw_payload?: {
    [k: string]: unknown;
  } | null;
  id: number;
  lead_id: number;
}
export interface LeadRead {
  created_at: string;
  updated_at: string;
  url: string;
  business_name?: string | null;
  sector?: string | null;
  country?: string;
  region?: string | null;
  id: number;
  builder_detected: BuilderType | null;
  builder_confidence: number | null;
  builder_evidence:
    | {
        [k: string]: unknown;
      }[]
    | null;
  emails: string[];
  phones: string[];
  social_links: {
    [k: string]: string;
  };
  status: LeadStatus;
  score: number;
  last_crawl_at: string | null;
  embedding_model: string | null;
  embedding_at: string | null;
}
export interface LeadUpdate {
  business_name?: string | null;
  sector?: string | null;
  region?: string | null;
  emails?: string[] | null;
  phones?: string[] | null;
  social_links?: {
    [k: string]: string;
  } | null;
  status?: LeadStatus | null;
  score?: number | null;
  builder_detected?: BuilderType | null;
  builder_confidence?: number | null;
  builder_evidence?:
    | {
        [k: string]: unknown;
      }[]
    | null;
}
export interface OptOutLogRead {
  id: number;
  email: string;
  lead_id_at_optout: number | null;
  channel: string;
  evidence: string | null;
  opted_out_at: string;
}
export interface OutreachSendRead {
  id: number;
  sequence_id: number;
  lead_id: number;
  step_index: number;
  channel: OutreachChannel;
  subject: string | null;
  body_rendered: string | null;
  status: OutreachSendStatus;
  sent_at: string | null;
  opened_at: string | null;
  replied_at: string | null;
  bounced_at: string | null;
  provider_message_id: string | null;
  created_at: string;
  updated_at: string;
}
export interface OutreachSequenceCreate {
  template_name: string;
  name: string;
  channel?: OutreachChannel1;
  steps_json: OutreachStep[];
  lead_id: number;
}
/**
 * Un paso dentro de steps_json — validado para asegurar mínimos LSSI-CE.
 */
export interface OutreachStep {
  step_index: number;
  subject?: string | null;
  body: string;
  delay_days_from_previous?: number;
  legal_footer_included?: boolean;
}
export interface OutreachSequenceRead {
  created_at: string;
  updated_at: string;
  template_name: string;
  name: string;
  channel?: OutreachChannel2;
  steps_json: OutreachStep[];
  id: number;
  lead_id: number;
  status: OutreachSequenceStatus;
  legal_validation_passed: boolean;
  legal_validator_version: string | null;
}
export interface ProjectCreate {
  client_name: string;
  source_url: string;
  target_domain?: string | null;
  builder_source?: BuilderType | null;
  has_ecommerce?: boolean;
  is_multilang?: boolean;
  langs?: string[];
  primary_lang?: string | null;
  asset_storage?: string;
  preserve_paths?: boolean;
  plan?: string | null;
  lead_id?: number | null;
  hosting_target_json?: {
    [k: string]: unknown;
  } | null;
}
export interface ProjectPhaseRead {
  id: number;
  project_id: number;
  phase_name: string;
  status: ProjectPhaseStatus;
  started_at: string | null;
  completed_at: string | null;
  attempt: number;
  error_log: string | null;
  output_summary: {
    [k: string]: unknown;
  } | null;
  created_at: string;
  updated_at: string;
}
export interface ProjectRead {
  created_at: string;
  updated_at: string;
  client_name: string;
  source_url: string;
  target_domain?: string | null;
  builder_source?: BuilderType | null;
  has_ecommerce?: boolean;
  is_multilang?: boolean;
  langs?: string[];
  primary_lang?: string | null;
  asset_storage?: string;
  preserve_paths?: boolean;
  plan?: string | null;
  id: number;
  lead_id: number | null;
  hosting_target_json: {
    [k: string]: unknown;
  } | null;
  theme_styles_origin: {
    [k: string]: unknown;
  } | null;
  visual_diff_avg_score: number | null;
  status: ProjectStatus;
  started_at: string | null;
  completed_at: string | null;
  estimated_go_live_at: string | null;
}
export interface ProjectUpdate {
  client_name?: string | null;
  target_domain?: string | null;
  builder_source?: BuilderType | null;
  has_ecommerce?: boolean | null;
  is_multilang?: boolean | null;
  langs?: string[] | null;
  primary_lang?: string | null;
  asset_storage?: string | null;
  preserve_paths?: boolean | null;
  status?: ProjectStatus | null;
  plan?: string | null;
  estimated_go_live_at?: string | null;
}
export interface ResidualTaskCreate {
  title: string;
  description: string;
  category: ResidualCategory;
  estimated_minutes?: number | null;
  screenshot_paths?: string[];
  generated_by?: string | null;
  assignee_hint?: string | null;
  project_id: number;
}
export interface ResidualTaskRead {
  created_at: string;
  updated_at: string;
  title: string;
  description: string;
  category: ResidualCategory;
  estimated_minutes?: number | null;
  screenshot_paths?: string[];
  generated_by?: string | null;
  assignee_hint?: string | null;
  id: number;
  project_id: number;
  clickup_task_id: string | null;
  status: ResidualStatus;
  closed_at: string | null;
}
export interface ScrapedPageRead {
  created_at: string;
  updated_at: string;
  id: number;
  project_id: number;
  url: string;
  slug?: string | null;
  title?: string | null;
  lang?: string | null;
  depth: number;
  screenshot_path: string | null;
  screenshot_mobile_path: string | null;
  status: ScrapeStatus;
  scraped_at: string | null;
  error_message: string | null;
}
export interface SeoRedirectRead {
  created_at: string;
  updated_at: string;
  id: number;
  project_id: number;
  source_path: string;
  target_path: string;
  http_status: number;
  wp_redirect_id: number | null;
}
export interface UserCreate {
  email: string;
  name: string;
  role?: UserRole;
  is_active?: boolean;
  password: string;
}
export interface UserRead {
  created_at: string;
  updated_at: string;
  email: string;
  name: string;
  role?: UserRole1;
  is_active?: boolean;
  id: string;
}
export interface WooProductRead {
  created_at: string;
  updated_at: string;
  id: number;
  project_id: number;
  source_id: string | null;
  sku: string;
  name: string;
  price?: string | null;
  currency?: string;
  stock?: number | null;
  stock_managed: boolean;
  attributes_json:
    | {
        [k: string]: unknown;
      }[]
    | null;
  variations_json:
    | {
        [k: string]: unknown;
      }[]
    | null;
  image_asset_ids: number[];
  categories: string[];
  wp_product_id: number | null;
}
export interface TimestampedRead {
  created_at: string;
  updated_at: string;
}
/**
 * Base con config estricta para todos los schemas Webcafeína Migrator.
 */
export interface WcmModel {}
export interface AssetBase {
  original_url: string;
  hash: string;
  mime?: string | null;
  size_bytes?: number | null;
  width?: number | null;
  height?: number | null;
  alt_text?: string | null;
}
export interface ContentBlockBase {
  block_type: BlockType;
  order_index: number;
  lang?: string | null;
  content_json?: {
    [k: string]: unknown;
  };
  source?: ContentBlockSource2;
}
export interface LeadBase {
  url: string;
  business_name?: string | null;
  sector?: string | null;
  country?: string;
  region?: string | null;
}
export interface LeadEnrichmentBase {
  source: string;
  employees_estimate?: number | null;
  revenue_estimate_eur?: number | null;
  tech_stack?: string[] | null;
  traffic_estimate_monthly?: number | null;
  ahrefs_dr?: number | null;
  legal_ground?: string | null;
  raw_payload?: {
    [k: string]: unknown;
  } | null;
}
export interface OutreachSequenceBase {
  template_name: string;
  name: string;
  channel?: OutreachChannel3;
  steps_json: OutreachStep[];
}
export interface ProjectBase {
  client_name: string;
  source_url: string;
  target_domain?: string | null;
  builder_source?: BuilderType | null;
  has_ecommerce?: boolean;
  is_multilang?: boolean;
  langs?: string[];
  primary_lang?: string | null;
  asset_storage?: string;
  preserve_paths?: boolean;
  plan?: string | null;
}
export interface ResidualTaskBase {
  title: string;
  description: string;
  category: ResidualCategory;
  estimated_minutes?: number | null;
  screenshot_paths?: string[];
  generated_by?: string | null;
  assignee_hint?: string | null;
}
export interface UserBase {
  email: string;
  name: string;
  role?: UserRole2;
  is_active?: boolean;
}
