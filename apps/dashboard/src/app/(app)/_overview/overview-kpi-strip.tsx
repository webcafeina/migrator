import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

import { cn } from "@/lib/utils";

export interface OverviewKpi {
  label: string;
  value: number | string;
  /** Si existe, el KPI es clickable. */
  href?: string;
  /** Si true, valor en color warning (típico para errores > 0). */
  accent?: boolean;
}

interface OverviewKpiStripProps {
  kpis: OverviewKpi[];
  className?: string;
}

/**
 * Tira horizontal de KPIs del Overview. Sustituye las 4 cards gigantes
 * de la versión anterior por una línea compacta con value grande +
 * label small + arrow indicador de "clickable" si hay href.
 *
 * Separadores verticales sutiles entre items. Tabular nums para que los
 * números mantengan ancho al cambiar.
 */
export function OverviewKpiStrip({ kpis, className }: OverviewKpiStripProps) {
  return (
    <ul
      className={cn(
        "flex divide-x divide-wcm-detail/40 overflow-hidden rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30",
        className,
      )}
    >
      {kpis.map((kpi) => (
        <li key={kpi.label} className="flex-1">
          <KpiCell kpi={kpi} />
        </li>
      ))}
    </ul>
  );
}

function KpiCell({ kpi }: { kpi: OverviewKpi }) {
  const body = (
    <div className="group flex h-full flex-col gap-1 px-5 py-3.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
          {kpi.label}
        </span>
        {kpi.href && (
          <ArrowUpRight
            className="h-3.5 w-3.5 text-muted-foreground group-hover:text-wcm-accent"
            aria-hidden
          />
        )}
      </div>
      <span
        className={cn(
          "text-2xl font-semibold leading-none tabular-nums tracking-tight",
          kpi.accent ? "text-wcm-warning" : "text-wcm-text",
        )}
      >
        {kpi.value}
      </span>
    </div>
  );

  if (kpi.href) {
    return (
      <Link href={kpi.href} className="block h-full hover:bg-wcm-secondary/60">
        {body}
      </Link>
    );
  }
  return body;
}
