/**
 * Etiquetas en castellano para enums del dominio.
 *
 * Punto único de traducción para los status que se muestran en UI. Los
 * enums del backend siguen en inglés (matching DB + API + tests); aquí
 * los traducimos solo a la hora de renderizar.
 *
 * Si un status llega sin traducción, devuelve el string original capitalizado.
 */

const LEAD_LABELS: Record<string, string> = {
  discovered: "Descubierto",
  fingerprinted: "Identificado",
  enriched: "Enriquecido",
  outreach_prepared: "Borrador preparado",
  outreach_sent: "Enviado",
  responded: "Respondido",
  converted: "Convertido",
  manual_review: "Revisión manual",
  opted_out: "Baja (RGPD)",
  discarded: "Descartado",
};

const PROJECT_LABELS: Record<string, string> = {
  queued: "En cola",
  running: "En ejecución",
  blocked_human_input: "Espera revisión",
  qa_failed: "Falló QA",
  completed: "Completado",
  cancelled: "Cancelado",
};

const PROJECT_PHASE_LABELS: Record<string, string> = {
  pending: "Pendiente",
  running: "En ejecución",
  completed: "Completado",
  failed: "Falló",
  skipped: "Omitido",
};

const RESIDUAL_LABELS: Record<string, string> = {
  open: "Abierta",
  in_progress: "En curso",
  blocked: "Bloqueada",
  done: "Hecha",
  skipped: "Omitida",
};

const OUTREACH_SEQUENCE_LABELS: Record<string, string> = {
  draft_pending_review: "Borrador pendiente",
  ready: "Lista para enviar",
  in_progress: "Enviando",
  completed: "Completada",
  paused: "Pausada",
  opted_out: "Baja (RGPD)",
  cancelled: "Cancelada",
};

const OUTREACH_SEND_LABELS: Record<string, string> = {
  queued: "En cola",
  sent: "Enviado",
  bounced: "Rebotado",
  opened: "Abierto",
  replied: "Respondido",
  failed: "Falló",
};

const ALL_LABELS: Record<string, string> = {
  ...LEAD_LABELS,
  ...PROJECT_LABELS,
  ...PROJECT_PHASE_LABELS,
  ...RESIDUAL_LABELS,
  ...OUTREACH_SEQUENCE_LABELS,
  ...OUTREACH_SEND_LABELS,
};

function capitalize(s: string): string {
  const first = s[0];
  return first ? first.toUpperCase() + s.slice(1) : s;
}

/**
 * Traduce un status de cualquier enum del dominio. Algunos valores se
 * solapan entre enums (ej. `running`, `completed`); en esos casos la
 * traducción es la misma, así que un mapa global basta.
 */
export function statusLabel(status: string | null | undefined): string {
  if (!status) return "—";
  const key = status.toLowerCase();
  return ALL_LABELS[key] ?? capitalize(status.replace(/_/g, " "));
}

/** Traducciones específicas si en algún sitio quieres forzar dominio. */
export const leadStatusLabel = (s: string) =>
  LEAD_LABELS[s.toLowerCase()] ?? statusLabel(s);

/** Status de la secuencia de contacto comercial (`OutreachSequenceStatus`). */
export const sequenceStatusLabel = (s: string) =>
  OUTREACH_SEQUENCE_LABELS[s.toLowerCase()] ?? statusLabel(s);

/** Status de cada envío individual (`OutreachSendStatus`). */
export const sendStatusLabel = (s: string) =>
  OUTREACH_SEND_LABELS[s.toLowerCase()] ?? statusLabel(s);
