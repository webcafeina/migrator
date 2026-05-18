"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import { toast } from "sonner";

import { ApiError, api } from "@/lib/api";
import {
  sendStatusLabel,
  sequenceStatusLabel,
} from "@/lib/labels";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { OutreachSequenceRead } from "@/types/api";

import {
  type EditableStep,
  SequenceStepEditor,
} from "./sequence-step-editor";

/**
 * Panel de contacto comercial del lead. Lista las sequences existentes
 * (típicamente 1 por lead) con cada paso desplegado y, según el status
 * de la sequence, los envíos reales asociados.
 *
 * Acciones disponibles por estado:
 *   DRAFT_PENDING_REVIEW + legal_passed → Aprobar | Cancelar
 *   READY                               → Enviar | Pausar | Cancelar
 *   IN_PROGRESS                         → Pausar | Cancelar
 *   PAUSED                              → Aprobar (reanudar) | Cancelar
 *   COMPLETED / OPTED_OUT / CANCELLED   → solo lectura
 *
 * Renombrado en v0.12.0 (ex `OutreachSequencePanel`) como parte del
 * refactor castellano. URLs/columnas BD siguen siendo `outreach`.
 */

interface SequenceDetailRead extends OutreachSequenceRead {
  sends?: SendRead[];
}

interface SendRead {
  id: number;
  sequence_id: number;
  lead_id: number;
  step_index: number;
  channel: string;
  subject: string | null;
  body_rendered: string | null;
  status: string;
  sent_at: string | null;
  opened_at: string | null;
  replied_at: string | null;
  bounced_at: string | null;
  provider_message_id: string | null;
  /** v0.13.2: mensaje legible del proveedor cuando status=FAILED
   * (ej. "Resend rechazó: domain not verified"). */
  error_message: string | null;
}

interface ContactSequencePanelProps {
  leadId: number;
}

export function ContactSequencePanel({ leadId }: ContactSequencePanelProps) {
  const [sequences, setSequences] = useState<SequenceDetailRead[] | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    api
      .get<OutreachSequenceRead[]>("/api/v1/outreach/sequences", {
        searchParams: { lead_id: leadId },
      })
      .then(async (list) => {
        if (!alive) return;
        // Para cada sequence cuyo status indique que ya hay envíos
        // (READY o posteriores), fetcheamos el detail para incluir
        // `sends`. DRAFT/PAUSED no tienen sends relevantes aún.
        const detailed = await Promise.all(
          list.map(async (seq) => {
            const status = String(seq.status).toUpperCase();
            const needsSends =
              status === "READY" ||
              status === "IN_PROGRESS" ||
              status === "COMPLETED";
            if (!needsSends) return seq as SequenceDetailRead;
            try {
              return await api.get<SequenceDetailRead>(
                `/api/v1/outreach/sequences/${seq.id}`,
              );
            } catch {
              return seq as SequenceDetailRead;
            }
          }),
        );
        if (alive) setSequences(detailed);
      })
      .catch((err) => {
        if (!alive) return;
        setError(
          err instanceof ApiError ? err.message : "Error al cargar contactos",
        );
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [leadId]);

  // Helper compartido: reemplaza UNA sequence en el state local con la
  // versión actualizada devuelta por una mutación (approve/pause/etc).
  // Fix del bug v0.12.0: router.refresh() NO re-fetchaba el Client
  // child (useEffect con [leadId] no se re-evalúa). Ahora cada acción
  // actualiza el state local con la response — UI consistente sin
  // depender del refresh del Server padre.
  const replaceSequence = useCallback(
    (updated: SequenceDetailRead) => {
      setSequences((prev) =>
        prev == null
          ? prev
          : prev.map((s) => (s.id === updated.id ? updated : s)),
      );
    },
    [],
  );

  if (loading) {
    return (
      <p className="text-xs text-muted-foreground">Cargando borradores…</p>
    );
  }
  if (error) {
    return (
      <p className="text-xs text-wcm-danger">
        No se pudieron cargar los borradores: {error}
      </p>
    );
  }
  if (!sequences || sequences.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        Sin borradores. Pulsa <strong>Componer contacto</strong> en la
        barra de acciones para generar uno.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {sequences.map((seq) => (
        <SequenceCard
          key={seq.id}
          sequence={seq}
          onUpdate={replaceSequence}
        />
      ))}
    </div>
  );
}

function SequenceCard({
  sequence,
  onUpdate,
}: {
  sequence: SequenceDetailRead;
  onUpdate: (updated: SequenceDetailRead) => void;
}) {
  const [pending, startTransition] = useTransition();
  const [localSteps, setLocalSteps] = useState<Record<string, unknown>[]>(
    (sequence.steps_json ?? []) as unknown as Record<string, unknown>[],
  );
  const [legalPassed, setLegalPassed] = useState<boolean>(
    sequence.legal_validation_passed,
  );
  const [editingIdx, setEditingIdx] = useState<number | null>(null);

  // Sincroniza state local cuando el padre nos pasa una sequence
  // updated (p. ej. tras approve → status cambia, sends aparecen).
  useEffect(() => {
    setLocalSteps(
      (sequence.steps_json ?? []) as unknown as Record<string, unknown>[],
    );
    setLegalPassed(sequence.legal_validation_passed);
  }, [sequence.steps_json, sequence.legal_validation_passed]);

  // Polling automático del detail mientras hay sends en estado no
  // terminal (queued/sending). Espejo del patrón LeadStatusPoller
  // v0.11.1. Refetcha cada 4s; para cuando todos los sends están en
  // terminal (sent/bounced/replied/failed) o cuando la sequence está
  // en COMPLETED/CANCELLED/OPTED_OUT.
  useEffect(() => {
    const hasInflightSends = (sequence.sends ?? []).some(
      (s) => s.status === "queued",
    );
    const seqStatus = String(sequence.status).toUpperCase();
    const isInflight =
      hasInflightSends || seqStatus === "IN_PROGRESS";
    if (!isInflight) return;
    const id = setInterval(async () => {
      try {
        const fresh = await api.get<SequenceDetailRead>(
          `/api/v1/outreach/sequences/${sequence.id}`,
        );
        onUpdate(fresh);
      } catch {
        /* mantiene state si el API falla puntualmente */
      }
    }, 4000);
    return () => clearInterval(id);
  }, [sequence.id, sequence.status, sequence.sends, onUpdate]);

  const status = String(sequence.status).toUpperCase();
  const editable =
    status === "DRAFT_PENDING_REVIEW" || status === "PAUSED";

  // Visibilidad del botón (status lo permite) vs habilitación (precondiciones
  // extras como legal_passed). Mostrar disabled con tooltip > esconder.
  const showApprove =
    status === "DRAFT_PENDING_REVIEW" || status === "PAUSED";
  const canApprove = showApprove && legalPassed;
  const canPause = status === "READY" || status === "IN_PROGRESS";
  const canCancel =
    status === "DRAFT_PENDING_REVIEW" ||
    status === "READY" ||
    status === "PAUSED";
  const canSend = status === "READY";

  function runTransition(action: "approve" | "pause" | "cancel") {
    startTransition(async () => {
      try {
        const updated = await api.post<OutreachSequenceRead>(
          `/api/v1/outreach/sequences/${sequence.id}/transition`,
          { action },
        );
        const newStatus = String(updated.status).toUpperCase();
        // Si pasa a READY o IN_PROGRESS, refetch detail para traer sends.
        let merged: SequenceDetailRead = updated;
        if (newStatus === "READY" || newStatus === "IN_PROGRESS") {
          try {
            merged = await api.get<SequenceDetailRead>(
              `/api/v1/outreach/sequences/${sequence.id}`,
            );
          } catch {
            /* mantenemos updated sin sends */
          }
        }
        onUpdate(merged);
        toast.success(
          `Secuencia #${sequence.id}: ${sequenceStatusLabel(updated.status)}`,
        );
      } catch (err) {
        const msg =
          err instanceof ApiError ? err.message : `Error al ${action}`;
        toast.error(msg);
      }
    });
  }

  function sendNow() {
    startTransition(async () => {
      try {
        const resp = await api.post<{ task_id?: string; status?: string }>(
          `/api/v1/outreach/sequences/${sequence.id}/send`,
        );
        // El send es asíncrono — encola el OutreachSend en Celery.
        // Refetchamos el detail para reflejar el nuevo estado y los
        // sends.
        const merged = await api.get<SequenceDetailRead>(
          `/api/v1/outreach/sequences/${sequence.id}`,
        );
        onUpdate(merged);
        toast.success(
          resp.task_id
            ? `Envío encolado · task ${resp.task_id.slice(0, 8)}…`
            : "Envío encolado",
        );
      } catch (err) {
        toast.error(
          err instanceof ApiError ? err.message : "Error al enviar",
        );
      }
    });
  }

  function saveStep(editedStep: EditableStep) {
    startTransition(async () => {
      const next = localSteps.map((s, idx) =>
        idx === editedStep.step_index ? editedStep : _toEditable(s, idx),
      );
      try {
        const updated = await api.patch<OutreachSequenceRead>(
          `/api/v1/outreach/sequences/${sequence.id}/steps`,
          { steps: next },
        );
        setLocalSteps(
          (updated.steps_json ?? []) as unknown as Record<string, unknown>[],
        );
        setLegalPassed(updated.legal_validation_passed);
        setEditingIdx(null);
        onUpdate(updated as SequenceDetailRead);
        if (updated.legal_validation_passed) {
          toast.success(`Paso ${editedStep.step_index + 1} guardado`);
        } else {
          toast.warning(
            "Paso guardado pero NO pasa validación legal — Aprobar deshabilitado",
          );
        }
      } catch (err) {
        toast.error(
          err instanceof ApiError ? err.message : "Error al guardar",
        );
      }
    });
  }

  return (
    <article className="rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-4">
      <header className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-wcm-text">
            {sequence.name}
          </div>
          <div className="mt-0.5 text-[11px] text-muted-foreground">
            <code className="text-wcm-text/80">{sequence.template_name}</code>
            {sequence.channel && (
              <>
                <span className="mx-1.5">·</span>
                {String(sequence.channel).toLowerCase()}
              </>
            )}
            <span className="mx-1.5">·</span>
            creada {formatRelativeTime(sequence.created_at)}
          </div>
        </div>
        <SequenceStatusBadge status={status} />
      </header>

      {!legalPassed && (status === "DRAFT_PENDING_REVIEW" || status === "PAUSED") && (
        <div className="mb-3 rounded-sm border border-wcm-danger/40 bg-wcm-danger/[0.05] px-2.5 py-1.5 text-[11px] text-wcm-danger">
          Validación legal NO pasada. No se puede aprobar — revisa el
          cuerpo del paso (firma + opt-out obligatorios).
        </div>
      )}

      <ol className="space-y-3">
        {localSteps.map((step, idx) => {
          const send = (sequence.sends ?? []).find(
            (s) => s.step_index === idx,
          );
          return editingIdx === idx ? (
            <li key={idx}>
              <SequenceStepEditor
                initialStep={_toEditable(step, idx)}
                onSave={saveStep}
                onCancel={() => setEditingIdx(null)}
                pending={pending}
              />
            </li>
          ) : (
            <StepBlock
              key={idx}
              step={step}
              idx={idx}
              send={send}
              onEdit={editable ? () => setEditingIdx(idx) : undefined}
            />
          );
        })}
      </ol>

      <footer className="mt-3 flex flex-wrap justify-end gap-2">
        {canCancel && (
          <button
            type="button"
            onClick={() => runTransition("cancel")}
            disabled={pending}
            className="rounded-sm border border-wcm-detail/60 px-3 py-1 text-xs text-wcm-danger hover:border-wcm-danger disabled:cursor-not-allowed disabled:opacity-50"
          >
            Cancelar
          </button>
        )}
        {canPause && (
          <button
            type="button"
            onClick={() => runTransition("pause")}
            disabled={pending}
            className="rounded-sm border border-wcm-warning/50 px-3 py-1 text-xs text-wcm-warning hover:border-wcm-warning disabled:cursor-not-allowed disabled:opacity-50"
          >
            Pausar
          </button>
        )}
        {showApprove && (
          <button
            type="button"
            onClick={() => runTransition("approve")}
            disabled={pending || !canApprove}
            title={
              canApprove
                ? "Aprobar la secuencia (queda lista para enviar)"
                : "Validación legal NO pasada — edita el paso afectado y restaura la firma + opt-out"
            }
            className="rounded-sm bg-wcm-accent px-3 py-1 text-xs font-semibold text-wcm-primary transition-colors hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending
              ? "Procesando…"
              : status === "PAUSED"
                ? "Reanudar →"
                : "Aprobar →"}
          </button>
        )}
        {canSend && (
          <button
            type="button"
            onClick={sendNow}
            disabled={pending}
            title="Encola el envío real vía Resend. Si RESEND_API_KEY no está configurado, el agente devolverá 'skipped' (no se envía nada, pero el sequence avanza)."
            className="rounded-sm bg-wcm-accent px-3 py-1 text-xs font-semibold text-wcm-primary transition-colors hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "Enviando…" : "Enviar ahora →"}
          </button>
        )}
        {!showApprove && !canPause && !canCancel && !canSend && (
          <span className="text-[11px] text-muted-foreground">
            Sin acciones disponibles en estado{" "}
            <strong>{sequenceStatusLabel(status)}</strong>
          </span>
        )}
      </footer>
    </article>
  );
}

function StepBlock({
  step,
  idx,
  send,
  onEdit,
}: {
  step: Record<string, unknown>;
  idx: number;
  send?: SendRead;
  onEdit?: () => void;
}) {
  const subject =
    typeof step.subject === "string" ? step.subject : "(sin asunto)";
  const body = typeof step.body === "string" ? step.body : "";
  const delay =
    typeof step.delay_days_from_previous === "number"
      ? step.delay_days_from_previous
      : typeof step.delay_days === "number"
        ? (step.delay_days as number)
        : null;

  return (
    <li className="rounded-sm border border-wcm-detail/30 bg-wcm-primary p-3">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2 text-[10.5px] uppercase tracking-wider text-muted-foreground">
        <span>
          Paso {idx + 1}
          {delay !== null && (
            <>
              <span className="mx-1.5">·</span>
              {delay === 0 ? "día 0" : `+${delay}d desde anterior`}
            </>
          )}
        </span>
        {onEdit && (
          <button
            type="button"
            onClick={onEdit}
            className="rounded-sm border border-wcm-detail/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-wcm-text/80 transition-colors hover:border-wcm-accent hover:text-wcm-accent"
          >
            Editar
          </button>
        )}
      </div>
      <div className="text-xs font-semibold text-wcm-text">{subject}</div>
      <pre className="mt-2 whitespace-pre-wrap break-words font-mono text-[11.5px] leading-relaxed text-wcm-text/90">
        {body}
      </pre>
      {send && <SendTracking send={send} />}
    </li>
  );
}

function SendTracking({ send }: { send: SendRead }) {
  const events: Array<[string, string | null]> = [
    ["encolado", null],
    ["enviado", send.sent_at],
    ["abierto", send.opened_at],
    ["respondido", send.replied_at],
    ["rebotado", send.bounced_at],
  ];
  return (
    <div className="mt-3 rounded-sm border border-wcm-detail/30 bg-wcm-secondary/30 p-2 text-[11px]">
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
          Envío real
        </span>
        <SendStatusBadge status={send.status} />
      </div>
      <ul className="space-y-0.5 text-wcm-text/80">
        {events
          .filter(([label, at]) => label === "encolado" || at !== null)
          .map(([label, at]) => (
            <li
              key={label}
              className="flex items-baseline justify-between gap-2"
            >
              <span className="text-muted-foreground">{label}</span>
              <span className="tabular-nums text-wcm-text/90">
                {at ? formatRelativeTime(at) : "—"}
              </span>
            </li>
          ))}
      </ul>
      {send.provider_message_id && (
        <p className="mt-1.5 text-[10px] text-muted-foreground">
          msg id:{" "}
          <code className="text-wcm-text/70">
            {send.provider_message_id}
          </code>
        </p>
      )}
      {send.error_message && (
        <div className="mt-2 rounded-sm border border-wcm-danger/40 bg-wcm-danger/[0.05] p-2 text-[11px] text-wcm-danger">
          <strong>Error del proveedor:</strong> {send.error_message}
        </div>
      )}
    </div>
  );
}

function SequenceStatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    DRAFT_PENDING_REVIEW:
      "border-wcm-warning/50 bg-wcm-warning/10 text-wcm-warning",
    READY: "border-wcm-accent/50 bg-wcm-accent/10 text-wcm-accent",
    IN_PROGRESS:
      "border-wcm-accent/50 bg-wcm-accent/10 text-wcm-accent",
    COMPLETED: "border-wcm-detail/60 text-wcm-text/80",
    PAUSED: "border-wcm-warning/40 text-wcm-warning",
    CANCELLED: "border-wcm-danger/40 text-wcm-danger",
    OPTED_OUT: "border-wcm-danger/40 text-wcm-danger",
  };
  const cls = map[status] ?? "border-wcm-detail/60 text-wcm-text/70";
  return (
    <span
      className={cn(
        "inline-flex shrink-0 rounded-sm border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wider",
        cls,
      )}
    >
      {sequenceStatusLabel(status)}
    </span>
  );
}

function SendStatusBadge({ status }: { status: string }) {
  const upper = status.toUpperCase();
  const map: Record<string, string> = {
    QUEUED: "border-wcm-detail/60 text-muted-foreground",
    SENT: "border-wcm-accent/50 bg-wcm-accent/10 text-wcm-accent",
    OPENED: "border-wcm-accent/50 bg-wcm-accent/10 text-wcm-accent",
    REPLIED:
      "border-wcm-accent/60 bg-wcm-accent/15 text-wcm-accent font-semibold",
    BOUNCED: "border-wcm-danger/40 text-wcm-danger",
    FAILED:
      "border-wcm-danger/50 bg-wcm-danger/15 text-wcm-danger font-semibold",
  };
  const cls = map[upper] ?? "border-wcm-detail/60 text-wcm-text/70";
  return (
    <span
      className={cn(
        "inline-flex rounded-sm border px-1.5 py-0.5 text-[10px] uppercase tracking-wider",
        cls,
      )}
    >
      {sendStatusLabel(status)}
    </span>
  );
}

/** Convierte un step heterogéneo al shape canónico `EditableStep`. */
function _toEditable(
  step: Record<string, unknown>,
  idx: number,
): EditableStep {
  const subjectRaw = step.subject;
  const subject = typeof subjectRaw === "string" ? subjectRaw : null;
  const body = typeof step.body === "string" ? step.body : "";
  const delay =
    typeof step.delay_days_from_previous === "number"
      ? step.delay_days_from_previous
      : typeof step.delay_days === "number"
        ? (step.delay_days as number)
        : 0;
  return {
    step_index: idx,
    subject,
    body,
    delay_days_from_previous: delay,
  };
}
