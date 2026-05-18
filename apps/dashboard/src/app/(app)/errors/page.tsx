import {
  FilterChips,
  type FilterChip,
} from "@/components/filter-chips";
import { KpiStrip, type Kpi } from "@/components/kpi-strip";
import { api } from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";
import type { ErrorLogRead } from "@/types/api";

import { ErrorsTable } from "./_components/errors-table";

interface ErrorStatsResponse {
  total: number;
  critical: number;
  error: number;
  warning: number;
  info: number;
  debug: number;
  distinct_components: number;
  last_critical_at: string | null;
}

interface SearchParams {
  /** Filtro por severidad (`ErrorSeverity` del backend). */
  severity?: string;
}

const SEVERITY_CHIPS_SOURCE = [
  ["critical", "crítico"],
  ["error", "error"],
  ["warning", "warning"],
  ["info", "info"],
  ["debug", "debug"],
] as const;

const SEVERITY_LABEL: Record<string, string> = Object.fromEntries(
  SEVERITY_CHIPS_SOURCE,
);

/**
 * `/errors` — rediseño consistente con el resto del flujo. Header
 * denso con KpiStrip por severidad + último crítico, chips de filtro
 * por severity, tabla densa con líneas relativas y componente
 * monospace.
 */
export default async function ErrorsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const [errors, stats] = await Promise.all([
    api
      .get<ErrorLogRead[]>("/api/v1/errors", {
        searchParams: {
          limit: 200,
          ...(params.severity ? { severity: params.severity } : {}),
        },
      })
      .catch(() => [] as ErrorLogRead[]),
    api
      .get<ErrorStatsResponse>("/api/v1/errors/stats")
      .catch(
        () =>
          ({
            total: 0,
            critical: 0,
            error: 0,
            warning: 0,
            info: 0,
            debug: 0,
            distinct_components: 0,
            last_critical_at: null,
          }) satisfies ErrorStatsResponse,
      ),
  ]);

  const kpis: Kpi[] = [
    { label: "Total (7d)", value: stats.total },
    {
      label: "Críticos",
      value: stats.critical,
      accent: stats.critical > 0,
    },
    { label: "Errores", value: stats.error, accent: stats.error > 0 },
    { label: "Warnings", value: stats.warning },
    { label: "Componentes", value: stats.distinct_components },
    {
      label: "Último crítico",
      value: stats.last_critical_at
        ? formatRelativeTime(stats.last_critical_at)
        : "—",
      accent: stats.last_critical_at != null,
    },
  ];

  const chips: FilterChip[] = SEVERITY_CHIPS_SOURCE.map(([value, label]) => ({
    id: `severity:${value}`,
    label,
    count: stats[value as keyof ErrorStatsResponse] as number,
    param: "severity",
    value,
  }));

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-lg font-semibold text-wcm-text">
          Errores recientes
        </h1>
        <p className="text-xs text-muted-foreground">
          Eventos del sistema en los últimos 7 días. Críticos y errores
          deberían ser cero en producción.
        </p>
      </header>

      <KpiStrip kpis={kpis} />

      <section className="space-y-3">
        <header className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            Listado
          </h2>
          <span className="text-[10.5px] tabular-nums text-muted-foreground">
            {`${errors.length} resultado${errors.length === 1 ? "" : "s"}`}
            {params.severity
              ? ` · filtrado por ${SEVERITY_LABEL[params.severity] ?? params.severity}`
              : ""}
          </span>
        </header>
        {stats.total > 0 && <FilterChips chips={chips} />}
        {errors.length === 0 ? (
          <EmptyErrors hasFilter={!!params.severity} systemEmpty={stats.total === 0} />
        ) : (
          <ErrorsTable errors={errors} />
        )}
      </section>
    </div>
  );
}

function EmptyErrors({
  hasFilter,
  systemEmpty,
}: {
  hasFilter: boolean;
  systemEmpty: boolean;
}) {
  if (systemEmpty) {
    return (
      <div className="rounded-sm border border-wcm-accent/30 bg-wcm-accent/[0.04] p-6">
        <div className="text-[10.5px] font-semibold uppercase tracking-[0.1em] text-wcm-accent">
          Sistema estable
        </div>
        <p className="mt-2 text-sm text-wcm-text/80">
          Sin errores registrados en los últimos 7 días. Excelente.
        </p>
        <p className="mt-2 text-xs text-muted-foreground">
          Para el detalle de cualquier error en producción, mira también
          Sentry (configurado en{" "}
          <code className="text-wcm-text">sentry.server.config.ts</code>)
          y journald del servidor.
        </p>
      </div>
    );
  }
  return (
    <div className="rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-6 text-center">
      <p className="text-sm text-wcm-text/70">
        {hasFilter
          ? "Sin errores con este filtro de severidad."
          : "Sin errores en la página actual."}
      </p>
    </div>
  );
}
