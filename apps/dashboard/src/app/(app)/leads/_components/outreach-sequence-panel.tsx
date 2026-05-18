"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import { toast } from "sonner";

import { ApiError, api } from "@/lib/api";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { OutreachSequenceRead } from "@/types/api";

interface OutreachSequencePanelProps {
  leadId: number;
}

/**
 * Panel de outreach del lead. Lista las sequences existentes (típicamente
 * 1 por lead) con cada paso desplegado: subject + body + delay desde el
 * paso anterior.
 *
 * Si la sequence está en `DRAFT_PENDING_REVIEW` y pasó la validación
 * legal, muestra el botón "Aprobar" que llama
 * `POST /outreach/sequences/{id}/transition` con `action="approve"`.
 *
 * Sustituye el placeholder vaporware del `DraftBanner` que apuntaba a
 * `#outreach` sin sección detrás (decisión del bloque 2 v0.11.1).
 */
export function OutreachSequencePanel({ leadId }: OutreachSequencePanelProps) {
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
        setError(err instanceof ApiError ? err.message : "Error al cargar outreach");
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
        Sin borradores. Pulsa <strong>Componer outreach</strong> en la
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
  const status = String(sequence.status);
  const canApprove =
    status === "DRAFT_PENDING_REVIEW" && sequence.legal_validation_passed;

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

      {!sequence.legal_validation_passed && (
        <div className="mb-3 rounded-sm border border-wcm-danger/40 bg-wcm-danger/[0.05] px-2.5 py-1.5 text-[11px] text-wcm-danger">
          Validación legal NO pasada. No se puede aprobar — revisa la
          plantilla.
        </div>
      )}

      <ol className="space-y-3">
        {(sequence.steps_json ?? []).map((step, idx) => (
          <StepBlock
            key={idx}
            step={step as unknown as Record<string, unknown>}
            idx={idx}
          />
        ))}
      </ol>

      <footer className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={approve}
          disabled={pending || !canApprove}
          title={
            canApprove
              ? "Aprobar la secuencia (queda lista para enviar)"
              : `No se puede aprobar desde estado ${status}`
          }
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
}: {
  step: Record<string, unknown>;
  idx: number;
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
      </div>
      <div className="text-xs font-semibold text-wcm-text">{subject}</div>
      <pre className="mt-2 whitespace-pre-wrap break-words font-mono text-[11.5px] leading-relaxed text-wcm-text/90">
        {body}
      </pre>
    </li>
  );
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
