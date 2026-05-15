import { cn } from "@/lib/utils";

interface ScorePanelProps {
  score: number;
  /** 0..100. Si está presente, se muestra como "p{percentile}". */
  percentile?: number | null;
  /** 0..100. Si está presente, se dibuja un tick vertical en la barra. */
  sectorMedian?: number | null;
  /** Nombre del sector para la línea de contexto. */
  sectorName?: string | null;
  className?: string;
}

/**
 * Score panel del rediseño master-detail (ADR-035 sucesor → ADR diseño).
 *
 * Cifra grande + barra horizontal + línea de contexto (percentil y
 * mediana del sector). Las tres capas refuerzan el mismo dato sin
 * repetirlo: número, posición visual, posición relativa.
 *
 * Si no recibe `percentile` o `sectorMedian`, las capas correspondientes
 * se omiten silenciosamente — útil para leads sin contexto agregado.
 */
export function ScorePanel({
  score,
  percentile,
  sectorMedian,
  sectorName,
  className,
}: ScorePanelProps) {
  const clamped = Math.max(0, Math.min(100, score));
  const delta =
    sectorMedian != null ? Math.round(clamped - sectorMedian) : null;

  return (
    <div className={cn("border-b border-wcm-detail/40 px-7 py-6", className)}>
      <div className="mb-3 text-[10.5px] uppercase tracking-[0.1em] text-muted-foreground">
        Score
      </div>

      <div className="grid grid-cols-[120px_1fr] items-center gap-7">
        <div className="text-[60px] font-bold leading-none tabular-nums tracking-tight">
          {clamped}
        </div>

        <div className="flex flex-col gap-1.5">
          <div className="relative h-2 rounded-[1px] bg-wcm-secondary">
            <div
              className="absolute inset-y-0 left-0 rounded-[1px] bg-wcm-accent"
              style={{ width: `${clamped}%` }}
            />
            {sectorMedian != null && (
              <div
                className="absolute -top-1 -bottom-1 w-px bg-muted-foreground"
                style={{ left: `${sectorMedian}%` }}
                aria-label={`Mediana del sector ${sectorName ?? ""}: ${sectorMedian}`}
              />
            )}
          </div>
          <div className="flex justify-between text-[9.5px] tracking-wide text-muted-foreground">
            <span>0</span>
            <span>100</span>
          </div>
        </div>
      </div>

      {(percentile != null || delta != null) && (
        <div className="mt-5 text-[11.5px] text-wcm-text/70">
          {percentile != null && (
            <>
              <strong className="font-semibold tabular-nums text-wcm-text">
                {`p${percentile}`}
              </strong>
              {` · top ${Math.max(1, 100 - percentile)}% del pipeline`}
            </>
          )}
          {delta != null && sectorName && (
            <>
              {percentile != null && " · "}
              <strong className="font-semibold text-wcm-text">
                {delta >= 0 ? `+${delta}` : delta}
              </strong>{" "}
              respecto a mediana del sector {sectorName}
            </>
          )}
        </div>
      )}
    </div>
  );
}
