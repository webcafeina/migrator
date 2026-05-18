import {
  AlertCircle,
  CheckCircle2,
  Circle,
  Loader2,
  MinusCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { cn, formatRelativeTime } from "@/lib/utils";
import type { ProjectPhaseRead } from "@/types/api";

interface ProjectPhasesTimelineProps {
  phases: ProjectPhaseRead[];
  className?: string;
}

/**
 * Timeline vertical de las fases del pipeline de migración. Cada fase
 * con icono por status, nombre, tiempo (relativo started/completed) +
 * duración cuando ambos timestamps existen, badge de reintento si
 * `attempt > 1`.
 *
 * Devuelve un mensaje contextual si la lista está vacía (proyecto sin
 * arrancar todavía).
 */
export function ProjectPhasesTimeline({
  phases,
  className,
}: ProjectPhasesTimelineProps) {
  if (phases.length === 0) {
    return (
      <div
        className={cn(
          "rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-6 text-center",
          className,
        )}
      >
        <p className="text-sm text-wcm-text/70">
          Pipeline sin arrancar todavía.
        </p>
        <p className="mt-2 text-xs text-muted-foreground">
          Pulsa &quot;Start&quot; arriba para encolar el pipeline completo
          (scrape → content → bricks → deploy → diff → checklist).
        </p>
      </div>
    );
  }

  return (
    <ol className={cn("relative flex flex-col", className)}>
      <span
        aria-hidden
        className="absolute left-[7px] top-3 bottom-3 w-px bg-wcm-detail/40"
      />
      {phases.map((p) => (
        <PhaseItem key={p.id} phase={p} />
      ))}
    </ol>
  );
}

function PhaseItem({ phase }: { phase: ProjectPhaseRead }) {
  const Icon = iconForStatus(phase.status);
  const colorCls = colorForStatus(phase.status);
  const when = whenLabel(phase);
  const duration = durationLabel(phase);

  return (
    <li className="relative grid grid-cols-[28px_1fr_auto] items-start gap-3 py-2.5">
      <Icon
        className={cn(
          "relative z-[1] mt-0.5 h-3.5 w-3.5 self-start rounded-full bg-wcm-primary",
          colorCls,
          phase.status === "running" && "animate-spin",
        )}
        aria-hidden
      />
      <div className="min-w-0">
        <div className="flex flex-wrap items-baseline gap-2">
          <span
            className={cn(
              "text-[13px] font-medium",
              phase.status === "pending"
                ? "text-wcm-text/60"
                : "text-wcm-text",
            )}
          >
            {phase.phase_name}
          </span>
          {phase.attempt > 1 && (
            <span className="rounded-sm border border-wcm-warning/40 px-1.5 text-[10px] font-semibold uppercase tracking-wider text-wcm-warning">
              {`intento ${phase.attempt}`}
            </span>
          )}
          <StatusPill status={phase.status} />
        </div>
        {phase.error_log && (
          <p className="mt-0.5 line-clamp-2 text-[11px] text-wcm-danger">
            {phase.error_log}
          </p>
        )}
      </div>
      <div className="self-start text-right text-[10.5px] tabular-nums text-muted-foreground">
        {when && <div>{when}</div>}
        {duration && (
          <div className="mt-0.5 text-wcm-text/60">{duration}</div>
        )}
      </div>
    </li>
  );
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    pending: {
      label: "pendiente",
      cls: "border-wcm-detail/60 text-muted-foreground",
    },
    running: {
      label: "en curso",
      cls: "border-wcm-accent/50 bg-wcm-accent/10 text-wcm-accent",
    },
    completed: {
      label: "ok",
      cls: "border-wcm-detail/60 text-wcm-text/70",
    },
    failed: {
      label: "fallo",
      cls: "border-wcm-danger/40 text-wcm-danger",
    },
    skipped: {
      label: "omitida",
      cls: "border-wcm-detail/60 text-muted-foreground",
    },
  };
  const spec = map[status] ?? {
    label: status,
    cls: "border-wcm-detail/60 text-muted-foreground",
  };
  return (
    <span
      className={cn(
        "rounded-sm border px-1.5 py-px text-[9.5px] uppercase tracking-wider",
        spec.cls,
      )}
    >
      {spec.label}
    </span>
  );
}

function iconForStatus(status: string): LucideIcon {
  switch (status) {
    case "completed":
      return CheckCircle2;
    case "running":
      return Loader2;
    case "failed":
      return AlertCircle;
    case "skipped":
      return MinusCircle;
    case "pending":
    default:
      return Circle;
  }
}

function colorForStatus(status: string): string {
  switch (status) {
    case "completed":
      return "text-wcm-accent";
    case "running":
      return "text-wcm-accent";
    case "failed":
      return "text-wcm-danger";
    case "skipped":
      return "text-muted-foreground";
    case "pending":
    default:
      return "text-muted-foreground";
  }
}

function whenLabel(phase: ProjectPhaseRead): string | null {
  if (phase.completed_at) return formatRelativeTime(phase.completed_at);
  if (phase.started_at)
    return `iniciada ${formatRelativeTime(phase.started_at)}`;
  return null;
}

function durationLabel(phase: ProjectPhaseRead): string | null {
  if (!phase.started_at || !phase.completed_at) return null;
  const ms =
    new Date(phase.completed_at).getTime() -
    new Date(phase.started_at).getTime();
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  if (m < 60) return rem > 0 ? `${m}m ${rem}s` : `${m}m`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}
