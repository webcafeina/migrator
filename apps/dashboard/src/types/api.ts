/**
 * Tipos del API.
 *
 * Reutilizamos los tipos generados por `pnpm gen:types` en
 * `packages/shared-types/ts/index.d.ts` (Pydantic → TS vía pydantic2ts).
 * Aquí solo re-exportamos los que el dashboard usa y añadimos alias
 * cortos donde aporta legibilidad.
 *
 * Si añades un campo en wcm_types/schemas/*.py, regenera con
 * `pnpm gen:types` y los tipos se actualizan automáticamente.
 */

import type {
  AssetRead,
  AuditLogRead,
  BricksPageRead,
  ContentBlockRead,
  ErrorLogRead,
  LeadCreate,
  LeadEnrichmentRead,
  LeadRead,
  LeadUpdate,
  OptOutLogRead,
  OutreachSendRead,
  OutreachSequenceCreate,
  OutreachSequenceRead,
  PreflightCheck,
  PreflightResult,
  ProjectCreate,
  ProjectPhaseRead,
  ProjectRead,
  ProjectUpdate,
  QaReportRead,
  ResidualTaskCreate,
  ResidualTaskRead,
  ScrapedPageRead,
  SeoRedirectRead,
  UserCreate,
  UserRead,
  VisualDiffRead,
  VisualDiffsListResponse,
  WebflowSourceCredentials,
  WixSourceCredentials,
  WooProductRead,
} from "@webcafeina/shared-types";

export type {
  AssetRead,
  AuditLogRead,
  BricksPageRead,
  ContentBlockRead,
  ErrorLogRead,
  LeadCreate,
  LeadEnrichmentRead,
  LeadRead,
  LeadUpdate,
  OptOutLogRead,
  OutreachSendRead,
  OutreachSequenceCreate,
  OutreachSequenceRead,
  PreflightCheck,
  PreflightResult,
  ProjectCreate,
  ProjectPhaseRead,
  ProjectRead,
  ProjectUpdate,
  QaReportRead,
  ResidualTaskCreate,
  ResidualTaskRead,
  ScrapedPageRead,
  SeoRedirectRead,
  UserCreate,
  UserRead,
  VisualDiffRead,
  VisualDiffsListResponse,
  WebflowSourceCredentials,
  WixSourceCredentials,
  WooProductRead,
};

// ---------- Tipos no generados ----------

/**
 * Response de endpoints "encolar task Celery". El API devuelve
 * `{task_id, status}` con metadatos según endpoint.
 */
export interface EnqueueResponse {
  task_id: string;
  status: "queued" | "not_implemented";
  [key: string]: unknown;
}

/**
 * Payload de alta bulk: hasta 200 URLs + metadata aplicada al batch.
 * Espejo de `wcm_types.schemas.leads.LeadBulkCreate`.
 */
export interface LeadBulkCreatePayload {
  urls: string[];
  business_name?: string;
  sector?: string;
  region?: string;
  country?: string;
}

/**
 * Detalle por URL fallida o duplicada. Espejo de
 * `wcm_types.schemas.leads.LeadBulkCreateOutcome`.
 */
export interface LeadBulkCreateOutcome {
  url: string;
  outcome: "skipped_duplicate" | "failed";
  lead_id?: number | null;
  reason?: string | null;
}

/**
 * Respuesta agregada de `POST /api/v1/leads/bulk`. `created` lleva
 * LeadRead completos para evitar follow-up fetches en el cliente.
 */
export interface LeadBulkCreateResult {
  created: LeadRead[];
  skipped_duplicates: LeadBulkCreateOutcome[];
  failed: LeadBulkCreateOutcome[];
}

/**
 * Snapshot de progreso de una campaña, retornado por
 * GET /api/v1/campaigns/runs/{task_id}.
 */
export interface CampaignRunStatus {
  task_id: string;
  state: "PENDING" | "STARTED" | "SUCCESS" | "FAILURE" | "RETRY";
  ready: boolean;
  prospect: {
    query: string | null;
    discovered: number;
    created: number;
    skipped_duplicate: number;
    skipped_no_website: number;
    skipped_excluded: number;
    skipped_blocked_type: number;
    warnings: string[];
  } | null;
  pipeline: {
    total: number;
    by_status: Record<string, number>;
    lead_ids: number[];
  } | null;
  error: string | null;
}
