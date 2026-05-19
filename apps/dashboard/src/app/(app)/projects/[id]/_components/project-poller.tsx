"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

interface ProjectPollerProps {
  /** Status actual del proyecto. Solo `running` y `queued` activan la vista viva. */
  status: string;
  /** ID del proyecto — necesario para abrir EventSource al canal correcto. */
  projectId: number;
  /** Fallback polling: frecuencia en ms si SSE no disponible. Default 2000. */
  fallbackIntervalMs?: number;
}

type Mode = "connecting" | "sse" | "polling";

/**
 * Vista viva del proyecto en marcha (v0.19.0).
 *
 * 1. Intenta abrir SSE a `/api/v1/projects/{id}/events`. Si conecta y
 *    recibe el `hello` inicial → modo SSE (sub-segundo, sin polling).
 *    Cada evento llama `router.refresh()` y el Server Component padre
 *    se re-renderiza con datos frescos.
 * 2. Si SSE falla (503, error, navegador sin soporte) → cae automáticamente
 *    al polling 2s tradicional (`setInterval(router.refresh, 2000)`).
 * 3. Cuando status pasa a terminal (completed/failed/cancelled), cierra
 *    la conexión SSE y/o el interval.
 *
 * El banner muestra el modo activo (SSE / polling) para diagnóstico.
 *
 * Patrón evolucionado de `LeadStatusPoller` con preferencia por SSE.
 */
export function ProjectPoller({
  status,
  projectId,
  fallbackIntervalMs = 2000,
}: ProjectPollerProps) {
  const router = useRouter();
  const isRunning = status === "running" || status === "queued";
  const [mode, setMode] = useState<Mode>("connecting");

  useEffect(() => {
    if (!isRunning) return;

    // Si el navegador no soporta EventSource, vamos directos a polling.
    if (typeof window === "undefined" || typeof EventSource === "undefined") {
      setMode("polling");
      const id = setInterval(() => router.refresh(), fallbackIntervalMs);
      return () => clearInterval(id);
    }

    let source: EventSource | null = null;
    let intervalId: ReturnType<typeof setInterval> | null = null;
    let fallenBack = false;

    function fallbackToPolling() {
      if (fallenBack) return;
      fallenBack = true;
      setMode("polling");
      if (source) {
        source.close();
        source = null;
      }
      intervalId = setInterval(() => router.refresh(), fallbackIntervalMs);
    }

    try {
      source = new EventSource(`/api/v1/projects/${projectId}/events`);
      source.onopen = () => setMode("sse");
      source.onmessage = (evt) => {
        // Cualquier mensaje del worker → re-fetch del Server Component.
        // El "hello" inicial también dispara un refresh inocuo (idempotente).
        if (evt.data) {
          router.refresh();
        }
      };
      source.onerror = () => {
        // EventSource intenta reconectar solo. Si el endpoint devolvió 503
        // (Redis no disponible), el estado del source quedará en CLOSED.
        if (source && source.readyState === EventSource.CLOSED) {
          fallbackToPolling();
        }
      };
    } catch {
      fallbackToPolling();
    }

    return () => {
      if (source) source.close();
      if (intervalId) clearInterval(intervalId);
    };
  }, [isRunning, projectId, fallbackIntervalMs, router]);

  if (!isRunning) return null;

  const label =
    status === "queued"
      ? "Pipeline encolado, esperando worker…"
      : "Pipeline en ejecución…";
  const modeLabel =
    mode === "sse"
      ? "vista viva · stream SSE"
      : mode === "polling"
        ? `vista viva · polling ${Math.round(fallbackIntervalMs / 1000)}s`
        : "vista viva · conectando…";

  return (
    <div
      role="status"
      aria-live="polite"
      data-mode={mode}
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
        <span className="ml-2 text-muted-foreground">{modeLabel}</span>
      </span>
    </div>
  );
}
