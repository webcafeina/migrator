"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { cn } from "@/lib/utils";

interface LeadStatusPollerProps {
  status: string;
  /** Frecuencia en ms. Default 4000 (suficiente para fingerprint ~5-15s y
   * enrich ~10-30s sin saturar la API). */
  intervalMs?: number;
}

/**
 * Polling de la ficha del lead mientras el pipeline está corriendo.
 *
 * - Si `status` indica "en curso" (discovered/fingerprinted) llama
 *   `router.refresh()` cada `intervalMs` ms. Next 15 refetcha el Server
 *   Component padre con datos frescos → el `lead.status` re-renderiza
 *   sin recargar la página.
 * - Cuando el status pasa a uno terminal (enriched, opted_out, etc.) el
 *   useEffect re-evalúa y desmonta el interval.
 * - Indicador visual mínimo (dot lima pulse + microcopy) para que el
 *   operador sepa que algo está pasando aunque la UI no cambie aún.
 *
 * Patrón espejo del polling de `/campaigns/runs/{task_id}` pero a nivel
 * lead individual.
 */
export function LeadStatusPoller({
  status,
  intervalMs = 4000,
}: LeadStatusPollerProps) {
  const router = useRouter();
  const isRunning = status === "discovered" || status === "fingerprinted";

  useEffect(() => {
    if (!isRunning) return;
    const id = setInterval(() => router.refresh(), intervalMs);
    return () => clearInterval(id);
  }, [isRunning, intervalMs, router]);

  if (!isRunning) return null;

  const label =
    status === "discovered"
      ? "Fingerprint en curso…"
      : "Enriquecimiento en curso…";

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex items-center gap-2 border-b border-wcm-accent/30 bg-wcm-accent/[0.05] px-7 py-2.5 text-[11px] text-wcm-text/80",
      )}
    >
      <span
        aria-hidden
        className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-wcm-accent shadow-[0_0_0_2px_rgba(177,241,0,0.18)]"
      />
      <span>
        <strong className="font-semibold text-wcm-accent">{label}</strong>
        <span className="ml-2 text-muted-foreground">
          actualizando cada {Math.round(intervalMs / 1000)}s · puedes seguir trabajando
        </span>
      </span>
    </div>
  );
}
