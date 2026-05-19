"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { cn } from "@/lib/utils";

interface ProjectPollerProps {
  /** Status actual del proyecto. Solo `running` (y `queued` justo tras Start) activa el polling. */
  status: string;
  /** Frecuencia en ms. Default 2000 — pipeline avanza típicamente cada 5-30s pero las
   *  fases cortas (notify, sync_clickup) cambian sub-5s y el operador debe verlo al instante. */
  intervalMs?: number;
}

/**
 * Polling de la ficha del proyecto mientras el pipeline está en marcha (v0.18.0).
 *
 * - Si `status` ∈ {queued, running}, llama `router.refresh()` cada `intervalMs`
 *   ms. Next 15 refetcha el Server Component padre → header, stepper y
 *   timeline se actualizan sin recargar manualmente.
 * - Cuando status pasa a terminal (completed/failed/cancelled/blocked) el
 *   `useEffect` re-evalúa y desmonta el interval.
 * - Banner mínimo visible (dot pulse + microcopy) confirma al operador que la
 *   vista está "viva" — sin esto cuesta saber si el dashboard está al día.
 *
 * Patrón espejo de `LeadStatusPoller` adaptado a frecuencia 2s (más agresiva)
 * y status del proyecto.
 */
export function ProjectPoller({
  status,
  intervalMs = 2000,
}: ProjectPollerProps) {
  const router = useRouter();
  const isRunning = status === "running" || status === "queued";

  useEffect(() => {
    if (!isRunning) return;
    const id = setInterval(() => router.refresh(), intervalMs);
    return () => clearInterval(id);
  }, [isRunning, intervalMs, router]);

  if (!isRunning) return null;

  const label =
    status === "queued"
      ? "Pipeline encolado, esperando worker…"
      : "Pipeline en ejecución…";

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex items-center gap-2 rounded-sm border border-wcm-accent/30 bg-wcm-accent/[0.05] px-3 py-2 text-[11px] text-wcm-text/80",
      )}
    >
      <span
        aria-hidden
        className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-wcm-accent shadow-[0_0_0_2px_rgba(177,241,0,0.18)]"
      />
      <span>
        <strong className="font-semibold text-wcm-accent">{label}</strong>
        <span className="ml-2 text-muted-foreground">
          vista viva · actualiza cada {Math.round(intervalMs / 1000)}s
        </span>
      </span>
    </div>
  );
}
