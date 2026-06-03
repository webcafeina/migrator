"use client";

import { useEffect } from "react";

import { formatUsd } from "@/lib/currency";
import { cn } from "@/lib/utils";

interface AggregationCostDialogProps {
  open: boolean;
  /** Cap de páginas configurado para el proyecto (max_pages_scrape). */
  maxPages: number;
  /** Coste estimado por página en USD del agregador semántico
   * (gpt-5.5 con cache). Default 0.01 USD. */
  costPerPageUsd?: number;
  onConfirm: () => void;
  onCancel: () => void;
  /** Si el botón "Confirmar" debe mostrar pending state (mientras
   * corre el POST /start tras confirmar). */
  pending?: boolean;
}

/**
 * Modal de confirmación de coste del BriefSectionAggregator (v0.29.0 B3).
 *
 * El agregador semántico (gpt-5.5) cuesta ~$0.01 por página. Para
 * proyectos pequeños (≤20 páginas) corre silencioso. Para proyectos
 * grandes muestra este modal con el coste estimado antes de quemar la
 * API de OpenAI sin que el operador lo sepa.
 *
 * Sin agregador el Hybrid resuelve 0.6% de secciones contra el catálogo
 * brickstemplate (bug WCM-053). Saltarlo (Cancelar) deja el pipeline
 * funcional pero con muchos residuals — operador puede volver al wizard
 * y bajar el cap, o aceptar el coste.
 */
export function AggregationCostDialog({
  open,
  maxPages,
  costPerPageUsd = 0.01,
  onConfirm,
  onCancel,
  pending = false,
}: AggregationCostDialogProps) {
  // Cerrar con Escape (solo si no está pending).
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !pending) onCancel();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, pending, onCancel]);

  if (!open) return null;

  const estimatedCost = maxPages * costPerPageUsd;
  const costLabel = formatUsd(estimatedCost);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="aggregation-cost-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !pending) onCancel();
      }}
    >
      <div
        className={cn(
          "w-full max-w-md rounded-sm border border-wcm-accent/40 bg-wcm-primary p-5 text-xs",
        )}
      >
        <h2
          id="aggregation-cost-title"
          className="text-sm font-semibold text-wcm-text"
        >
          Confirmar coste del agregador semántico
        </h2>

        <p className="mt-3 text-wcm-text/80">
          Este proyecto procesará hasta{" "}
          <strong className="text-wcm-text">{maxPages} páginas</strong>. El
          agregador semántico (gpt-5.5) reagrupa los bloques HTML del scraper
          en secciones canónicas (hero, features, cta, …) que matchean el
          catálogo brickstemplate. Sin él el Hybrid resuelve menos del 1% de
          secciones.
        </p>

        <div className="mt-4 rounded-sm border border-wcm-detail/40 bg-wcm-secondary/40 p-3">
          <dl className="grid grid-cols-[1fr_auto] gap-y-1.5 text-[11.5px]">
            <dt className="text-wcm-text/70">Páginas máximas</dt>
            <dd className="text-right font-mono text-wcm-text">{maxPages}</dd>
            <dt className="text-wcm-text/70">Coste por página</dt>
            <dd className="text-right font-mono text-wcm-text">
              {formatUsd(costPerPageUsd)}
            </dd>
            <dt className="border-t border-wcm-detail/30 pt-1.5 text-wcm-text">
              Coste máximo estimado
            </dt>
            <dd className="border-t border-wcm-detail/30 pt-1.5 text-right font-mono font-semibold text-wcm-accent">
              {costLabel}
            </dd>
          </dl>
        </div>

        <p className="mt-3 text-[11px] text-wcm-text/60">
          Coste real probablemente inferior por cache (re-runs sobre el mismo
          contenido son gratuitos) y por páginas triviales (fast-path sin
          LLM). El coste real se acumula en{" "}
          <code className="text-wcm-text/80">brief_aggregation_cost_usd</code>{" "}
          y se muestra en /preview tras el pipeline.
        </p>

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={pending}
            className="rounded-sm border border-wcm-detail/60 px-3 py-1 text-xs text-wcm-text/80 hover:border-wcm-detail hover:text-wcm-text disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={pending}
            className="rounded-sm bg-wcm-accent px-3 py-1 text-xs font-semibold text-wcm-primary hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "Arrancando…" : `Confirmar y arrancar (≤ ${costLabel})`}
          </button>
        </div>
      </div>
    </div>
  );
}
