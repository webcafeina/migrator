// AUTO-GENERATED FILE. DO NOT EDIT MANUALLY.
// Source: packages/shared-types/python/wcm_types/
// Regenerate with: pnpm gen:types  (or bash scripts/gen-ts.sh)
// Generated at: 2026-05-19T09:51:20Z

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
  | "test_send"
  | "opt_out"
  | "deploy"
  | "qa"
  | "system"
  | "email_layout_update";
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
export type UserRole3 = "admin" | "operator" | "viewer";

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
 *
 * Usado por:
 * - `POST /api/v1/leads` (alta manual desde dashboard o CLI).
 * - ProspectorAgent internamente al insertar leads descubiertos por
 *   campaña (no recibe esto vía HTTP, construye el modelo directamente).
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
  body_html_rendered?: string | null;
  status: OutreachSendStatus;
  sent_at: string | null;
  opened_at: string | null;
  replied_at: string | null;
  bounced_at: string | null;
  provider_message_id: string | null;
  error_message?: string | null;
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
 *
 * Tolerante con shapes legacy (fix v0.11.1): sequences viejas
 * persistidas en BD tienen `delay_days` (sin `_from_previous`) y
 * pueden traer campos extra (`template`). Para no romper su lectura
 * desde el dashboard:
 *
 * - `step_index` opcional con default 0 (se infiere del orden si falta).
 * - `delay_days_from_previous` acepta también el alias `delay_days`
 *   vía `AliasChoices`.
 * - `extra="allow"` permite cualquier campo adicional sin lanzar 500.
 *   Los composers nuevos siguen escribiendo solo el shape canónico.
 */
export interface OutreachStep {
  step_index?: number;
  subject?: string | null;
  body: string;
  delay_days_from_previous?: number;
  legal_footer_included?: boolean;
  [k: string]: unknown;
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
  checklist_md_url?: string | null;
  checklist_pdf_url?: string | null;
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
/**
 * Lectura de la última fila `qa_reports` de un proyecto.
 *
 * Scores Lighthouse normalizados 0-100. NULL = no medido (Lighthouse
 * no estaba disponible). Counts de errores HTML / broken links son
 * siempre enteros (>=0). Booleanos del bloque "checks binarios"
 * pueden ser None si la comprobación se skippeó.
 *
 * `report_json` lleva detalle drill-down (Lighthouse JSON completo,
 * lista de errores HTML, lista de links rotos) sin necesidad de
 * re-ejecutar el agent.
 */
export interface QaReportRead {
  created_at: string;
  updated_at: string;
  id: number;
  project_id: number;
  lighthouse_perf_desktop?: number | null;
  lighthouse_perf_mobile?: number | null;
  lighthouse_a11y_avg?: number | null;
  lighthouse_best_practices_avg?: number | null;
  lighthouse_seo_avg?: number | null;
  html_validator_errors_count?: number;
  html_validator_warnings_count?: number;
  broken_links_count?: number;
  total_links_checked?: number;
  https_valid?: boolean | null;
  robots_accessible?: boolean | null;
  sitemap_accessible?: boolean | null;
  report_json?: {
    [k: string]: unknown;
  } | null;
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
/**
 * Lectura de una fila `visual_diffs` desde el API.
 *
 * Una fila por página del proyecto comparada. Score 0-1 (1=idénticas).
 * URLs apuntan a R2 (si configurado) o `file://...` local fallback.
 */
export interface VisualDiffRead {
  created_at: string;
  updated_at: string;
  id: number;
  project_id: number;
  page_path: string;
  source_screenshot_url?: string | null;
  target_screenshot_url?: string | null;
  overlay_url?: string | null;
  score?: number | null;
  viewport_width?: number;
}
/**
 * Respuesta del endpoint `GET /projects/{id}/visual-diffs`.
 *
 * `avg_score` es el promedio de scores no-nulos (también persistido
 * en `projects.visual_diff_avg_score` para mostrar en header).
 * `pages_total` indica cuántas comparaciones se hicieron.
 */
export interface VisualDiffsListResponse {
  project_id: number;
  avg_score?: number | null;
  pages_total: number;
  pages: VisualDiffRead[];
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
/**
 * Alta de múltiples leads en una sola request.
 *
 * Los campos opcionales (sector, region, country, business_name) se
 * aplican a TODAS las URLs del batch — útil cuando el operador pega
 * una lista homogénea (todas del mismo sector/región).
 */
export interface LeadBulkCreate {
  /**
   * @minItems 1
   * @maxItems 200
   */
  urls: [string, ...string[]];
  business_name?: string | null;
  sector?: string | null;
  country?: string;
  region?: string | null;
}
/**
 * Detalle por URL fallida o duplicada en un alta bulk.
 *
 * `lead_id` se rellena cuando el outcome es 'skipped_duplicate' (id
 * del lead existente que ya tenía la URL). `reason` se rellena cuando
 * el outcome es 'failed'.
 */
export interface LeadBulkCreateOutcome {
  url: string;
  outcome: string;
  lead_id?: number | null;
  reason?: string | null;
}
/**
 * Respuesta agregada del `POST /api/v1/leads/bulk`.
 *
 * Listas separadas para facilitar el render en dashboard sin tener
 * que filtrar por outcome. `created` lleva LeadRead completos para
 * que el cliente no tenga que hacer follow-up fetches.
 */
export interface LeadBulkCreateResult {
  created: LeadRead[];
  skipped_duplicates: LeadBulkCreateOutcome[];
  failed: LeadBulkCreateOutcome[];
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
/**
 * Lectura del singleton `email_layouts` (id=1).
 *
 * Cualquier admin puede leerlo. La UI de `/settings/email-layout` lo
 * usa para hidratar el editor inicial.
 */
export interface EmailLayoutRead {
  created_at: string;
  updated_at: string;
  id: number;
  layout_html: string;
  layout_css: string;
  theme_config?: EmailLayoutTheme | null;
  updated_by_user_id?: string | null;
}
/**
 * Configuración del tema visual del layout maestro (v0.15.0).
 *
 * Cuando el operador edita desde el tab "Visual" de `/settings/email-layout`,
 * este JSON se persiste en `email_layouts.theme_config` y el backend
 * regenera `layout_html` + `layout_css` desde la plantilla canónica
 * de Webcafeína usando estos valores.
 *
 * Todos los campos tienen defaults que coinciden con la marca
 * Webcafeína (acento lima `#B1F100` sobre fondo claro, system-ui).
 * El form los puede sobrescribir todos.
 *
 * Validaciones:
 * - Colores: HEX 6 chars (`#RRGGBB`).
 * - Dimensiones: bounds razonables para email (ancho 320-720, padding 0-64,
 *   radius 0-12). Valores fuera de rango → 422.
 * - Tipografía: literal limitado a opciones email-safe.
 */
export interface EmailLayoutTheme {
  cta_bg?: string;
  cta_text?: string;
  cta_border?: string;
  page_bg?: string;
  card_bg?: string;
  card_border?: string;
  text_color?: string;
  text_strong?: string;
  link_color?: string;
  footer_text?: string;
  /**
   * Color del acento de marca ('í' de webcafeína cuando se usa texto en lugar de logo).
   */
  brand_accent?: string;
  show_logo?: boolean;
  /**
   * URL alternativa para el logo de este tema. Si None, usa EMAIL_LOGO_URL del env.
   */
  logo_url_override?: string | null;
  logo_max_width_px?: number;
  font_family?: "system-ui" | "serif" | "Inter";
  body_font_size_px?: number;
  body_line_height?: number;
  brand_text_size_px?: number;
  card_max_width_px?: number;
  content_padding_px?: number;
  header_padding_px?: number;
  footer_padding_px?: number;
  card_border_radius_px?: number;
  cta_border_radius_px?: number;
  card_border_width_px?: number;
}
/**
 * PUT /email-layout. v0.15.0 ahora acepta 3 modos:
 *
 * 1. Solo `theme_config` → backend regenera `layout_html` y `layout_css`
 *    desde la plantilla canónica.
 * 2. Solo `layout_html` + `layout_css` → backend persiste tal cual y
 *    borra `theme_config` (modo Código avanzado).
 * 3. Los 3 campos → respeta `theme_config` y usa el HTML/CSS que
 *    acompañe (útil si el frontend ya regeneró client-side por consistencia).
 *
 * Validaciones mínimas: si llega `layout_html` debe tener min 1 char
 * (no se permite vaciar el layout completamente).
 */
export interface EmailLayoutUpdate {
  layout_html?: string | null;
  layout_css?: string | null;
  theme_config?: EmailLayoutTheme | null;
  clear_theme?: boolean;
}
/**
 * Respuesta de los endpoints preview (template y step).
 *
 * El `html` ya viene con CSS inlined por premailer — listo para
 * pintar en un iframe `srcDoc`. El `subject` lo retornamos solo en
 * el preview de plantilla (con contexto mockeado); en preview de
 * step ya hay subject persistido y la UI lo conoce, pero lo
 * incluimos también para consistencia.
 */
export interface OutreachPreviewResponse {
  html: string;
  subject?: string | null;
}
export interface OutreachSequenceBase {
  template_name: string;
  name: string;
  channel?: OutreachChannel3;
  steps_json: OutreachStep[];
}
/**
 * Payload para editar un paso desde la UI. NO se permite cambiar
 * step_index (preserva orden del template original); add/delete steps
 * se hace re-componiendo el draft, no editando.
 */
export interface OutreachStepEdit {
  step_index: number;
  subject?: string | null;
  body: string;
  delay_days_from_previous?: number;
}
/**
 * PATCH /sequences/{id}/steps. La lista debe contener TODOS los
 * steps de la sequence (semántica de reemplazo, no patch parcial)
 * para que la validación legal se corra sobre el resultado completo.
 */
export interface OutreachStepsUpdatePayload {
  /**
   * @minItems 1
   * @maxItems 10
   */
  steps:
    | [OutreachStepEdit]
    | [OutreachStepEdit, OutreachStepEdit]
    | [OutreachStepEdit, OutreachStepEdit, OutreachStepEdit]
    | [OutreachStepEdit, OutreachStepEdit, OutreachStepEdit, OutreachStepEdit]
    | [OutreachStepEdit, OutreachStepEdit, OutreachStepEdit, OutreachStepEdit, OutreachStepEdit]
    | [OutreachStepEdit, OutreachStepEdit, OutreachStepEdit, OutreachStepEdit, OutreachStepEdit, OutreachStepEdit]
    | [
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit
      ]
    | [
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit
      ]
    | [
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit
      ]
    | [
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit,
        OutreachStepEdit
      ];
}
/**
 * Plantilla Jinja2 reutilizable usada por el composer al generar
 * drafts. v0.12.0 — migrada de fichero `.j2` a tabla BD editable.
 * v0.14.0 — añadidos `body_html_template` (HTML opcional) y CTA.
 */
export interface OutreachTemplateBase {
  name: string;
  subject_template: string;
  body_template: string;
  language?: string;
  body_html_template?: string | null;
  cta_label?: string | null;
  cta_url?: string | null;
}
/**
 * Crear plantilla nueva. `name` debe ser único.
 */
export interface OutreachTemplateCreate {
  name: string;
  subject_template: string;
  body_template: string;
  language?: string;
  body_html_template?: string | null;
  cta_label?: string | null;
  cta_url?: string | null;
}
export interface OutreachTemplateRead {
  created_at: string;
  updated_at: string;
  name: string;
  subject_template: string;
  body_template: string;
  language?: string;
  body_html_template?: string | null;
  cta_label?: string | null;
  cta_url?: string | null;
  id: number;
}
/**
 * Actualizar plantilla existente. Todos los campos opcionales —
 * `name` NO se cambia (es la clave por la que el composer la
 * resuelve; renombrar rompería sequences históricas que la
 * referencian).
 */
export interface OutreachTemplateUpdate {
  subject_template?: string | null;
  body_template?: string | null;
  language?: string | null;
  body_html_template?: string | null;
  cta_label?: string | null;
  cta_url?: string | null;
}
/**
 * POST /outreach/sequences/{id}/steps/{idx}/test-send.
 *
 * El operador escribe libremente el destino (puede ser su email
 * personal, otro Webcafeínero, etc.) para verificar visualmente que
 * el correo llega bien antes de aprobar el envío real al lead.
 */
export interface OutreachTestSendPayload {
  to: string;
}
/**
 * Resultado del envío de prueba.
 */
export interface OutreachTestSendResponse {
  provider_message_id: string | null;
  to: string;
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
/**
 * PATCH `/users/{id}` admin-only — cambiar rol, desactivar, renombrar.
 * `email` no editable (identidad). `password` requeriría flujo de
 * cambio con verificación que NO está en MVP.
 */
export interface UserUpdate {
  role?: UserRole3 | null;
  is_active?: boolean | null;
  name?: string | null;
}
