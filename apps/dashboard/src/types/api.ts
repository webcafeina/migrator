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
  ProjectCreate,
  ProjectPhaseRead,
  ProjectRead,
  ProjectUpdate,
  ResidualTaskCreate,
  ResidualTaskRead,
  ScrapedPageRead,
  SeoRedirectRead,
  UserCreate,
  UserRead,
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
  ProjectCreate,
  ProjectPhaseRead,
  ProjectRead,
  ProjectUpdate,
  ResidualTaskCreate,
  ResidualTaskRead,
  ScrapedPageRead,
  SeoRedirectRead,
  UserCreate,
  UserRead,
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
