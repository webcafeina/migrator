"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import { toast } from "sonner";

import { ApiError, api } from "@/lib/api";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { OutreachSequenceRead } from "@/types/api";

import {
  type EditableStep,
  SequenceStepEditor,
} from "./sequence-step-editor";

interface ContactSequencePanelProps {
  leadId: number;
}

/**
 * Panel de contacto comercial del lead. Lista las sequences
 * existentes (típicamente 1 por lead) con cada paso desplegado:
 * subject + body + delay desde el paso anterior.
 *
 * Si la sequence está en `DRAFT_PENDING_REVIEW` y pasó la validación
 * legal, muestra el botón "Aprobar" que llama
 * `POST /outreach/sequences/{id}/transition` con `action="approve"`.
 *
 * Sustituye el placeholder vaporware del `DraftBanner` que apuntaba a
 * `#outreach` sin sección detrás (decisión del bloque 2 v0.11.1).
 *
 * Renombrado en v0.12.0 (ex `OutreachSequencePanel`) como parte del
 * refactor castellano. Las URLs/columnas BD siguen siendo `outreach`
 * (ancla técnica estable).
 */
export function ContactSequencePanel({ leadId }: ContactSequencePanelProps) {
  const router = useRouter();
  const [sequences, setSequences] = useState<OutreachSequenceRead[] | null>(
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
      .then((data) => {
        if (!alive) return;
        setSequences(data);
      })
      .catch((err) => {
        if (!alive) return;
        setError(err instanceof ApiError ? err.message : "Error al cargar contactos");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [leadId]);

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
          onApproved={() => router.refresh()}
        />
      ))}
    </div>
  );
}

function SequenceCard({
  sequence,
  onApproved,
}: {
  sequence: OutreachSequenceRead;
  onApproved: () => void;
}) {
  const [pending, startTransition] = useTransition();
  // Estado local de los pasos para permitir edición optimista sin
  // refresh entre cada save. Se inicializa con los steps del prop y
  // se sustituye con la respuesta del PATCH (que recarga
  // legal_validation_passed con el resultado de la re-validación).
  const [localSteps, setLocalSteps] = useState<Record<string, unknown>[]>(
    (sequence.steps_json ?? []) as unknown as Record<string, unknown>[],
  );
  const [legalPassed, setLegalPassed] = useState<boolean>(
    sequence.legal_validation_passed,
  );
  const [editingIdx, setEditingIdx] = useState<number | null>(null);

  // El API serializa el enum lowercase (`'draft_pending_review'`),
  // así que normalizamos a UPPERCASE una vez antes de comparar.
  // Los OutreachSequenceStatus de wcm_types tienen valor lowercase
  // pero las constantes lógicas de UI las mantenemos UPPERCASE por
  // legibilidad (matchean el nombre del enum Python).
  const status = String(sequence.status).toUpperCase();
  const editable =
    status === "DRAFT_PENDING_REVIEW" || status === "PAUSED";
  const canApprove = status === "DRAFT_PENDING_REVIEW" && legalPassed;

  function approve() {
    startTransition(async () => {
      try {
        await api.post(
          `/api/v1/outreach/sequences/${sequence.id}/transition`,
          { action: "approve" },
        );
        toast.success(`Sequence #${sequence.id} aprobada — lista para enviar`);
        onApproved();
      } catch (err) {
        toast.error(
          err instanceof ApiError ? err.message : "Error al aprobar",
        );
      }
    });
  }

  function saveStep(editedStep: EditableStep) {
    startTransition(async () => {
      // Construir la lista completa: el paso editado + los demás
      // intactos. La API requiere semántica de reemplazo (PUT-like).
      const next = localSteps.map((s, idx) => {
        if (idx !== editedStep.step_index) {
          return _toEditable(s, idx);
        }
        return editedStep;
      });
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
        if (updated.legal_validation_passed) {
          toast.success(`Paso ${editedStep.step_index + 1} guardado`);
        } else {
          toast.warning(
            `Paso guardado pero NO pasa validación legal — Aprobar deshabilitado`,
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

      {!legalPassed && (
        <div className="mb-3 rounded-sm border border-wcm-danger/40 bg-wcm-danger/[0.05] px-2.5 py-1.5 text-[11px] text-wcm-danger">
          Validación legal NO pasada. No se puede aprobar — revisa el
          cuerpo del paso (firma + opt-out obligatorios).
        </div>
      )}

      <ol className="space-y-3">
        {localSteps.map((step, idx) =>
          editingIdx === idx ? (
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
              onEdit={editable ? () => setEditingIdx(idx) : undefined}
            />
          ),
        )}
      </ol>

      <footer className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={approve}
          disabled={pending || !canApprove}
          title={approveDisabledReason(status, legalPassed) ?? undefined}
          className="rounded-sm bg-wcm-accent px-3 py-1 text-xs font-semibold text-wcm-primary transition-colors hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {pending ? "Aprobando…" : "Aprobar →"}
        </button>
      </footer>
    </article>
  );
}

/** Render defensivo de cada step. El shape canónico tiene `subject` +
 * `body` + `delay_days_from_previous`, pero algunas sequences viejas
 * traen `delay_days` (sin "from_previous") — leemos ambos. */
function StepBlock({
  step,
  idx,
  onEdit,
}: {
  step: Record<string, unknown>;
  idx: number;
  /** Si se pasa, renderiza botón "Editar" que dispara el callback.
   * Si no, el paso es solo lectura (ej. sequence ya SENT/READY). */
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
    </li>
  );
}

/** Convierte un step del payload (heterogéneo) al shape canónico
 * `EditableStep` que espera el editor + el PATCH endpoint. */
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

function SequenceStatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    DRAFT_PENDING_REVIEW:
      "border-wcm-warning/50 bg-wcm-warning/10 text-wcm-warning",
    READY: "border-wcm-accent/50 bg-wcm-accent/10 text-wcm-accent",
    SENDING: "border-wcm-accent/50 bg-wcm-accent/10 text-wcm-accent",
    SENT: "border-wcm-detail/60 text-wcm-text/80",
    PAUSED: "border-wcm-detail/60 text-muted-foreground",
    CANCELLED: "border-wcm-danger/40 text-wcm-danger",
  };
  const cls = map[status] ?? "border-wcm-detail/60 text-wcm-text/70";
  return (
    <span
      className={cn(
        "inline-flex shrink-0 rounded-sm border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wider",
        cls,
      )}
    >
      {status.replace(/_/g, " ").toLowerCase()}
    </span>
  );
}

/** Razón por la que el botón Aprobar está deshabilitado. Devuelve
 * null si SE PUEDE aprobar (no hace falta tooltip). Distingue los 2
 * casos importantes para el operador: status no aprobable vs validación
 * legal fallida (el segundo es accionable — el operador puede editar
 * el paso problemático para restaurar la firma legal). */
function approveDisabledReason(
  status: string,
  legalPassed: boolean,
): string | null {
  if (status !== "DRAFT_PENDING_REVIEW") {
    return `Solo se aprueban borradores. Estado actual: ${status.replace(/_/g, " ").toLowerCase()}.`;
  }
  if (!legalPassed) {
    return "Validación legal NO pasada — revisa que el body de cada paso conserve la firma (razón social, CIF, dirección) y el enlace de opt-out.";
  }
  return null;
}
