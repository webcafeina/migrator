import {
  FilterChips,
  type FilterChip,
} from "@/components/filter-chips";
import { KpiStrip, type Kpi } from "@/components/kpi-strip";
import { api } from "@/lib/api";
import type { ResidualTaskRead } from "@/types/api";

import { ResidualTasksTable } from "./_components/residual-tasks-table";

interface ResidualStatsResponse {
  total: number;
  open: number;
  in_progress: number;
  blocked: number;
  done: number;
  skipped: number;
  blocking_go_live: number;
  distinct_projects: number;
  estimated_minutes_pending: number;
}

interface SearchParams {
  /** Filtro por status (`ResidualStatus` del backend). */
  status?: string;
}

const STATUS_CHIPS_SOURCE = [
  ["open", "abiertas"],
  ["in_progress", "en curso"],
  ["blocked", "bloqueadas"],
  ["done", "cerradas"],
  ["skipped", "omitidas"],
] as const;

const STATUS_LABEL: Record<string, string> = Object.fromEntries(
  STATUS_CHIPS_SOURCE,
);

/**
 * `/residual-tasks` — vista global de tareas residuales de TODOS los
 * proyectos. Distinta del checklist por proyecto
 * (`/projects/[id]/checklist`) — aquí el operador ve la carga total
 * de trabajo manual pendiente repartido en proyectos.
 */
export default async function ResidualTasksPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const [tasks, stats] = await Promise.all([
    api
      .get<ResidualTaskRead[]>("/api/v1/residual-tasks", {
        searchParams: params.status ? { status_filter: params.status } : {},
      })
      .catch(() => [] as ResidualTaskRead[]),
    api
      .get<ResidualStatsResponse>("/api/v1/residual-tasks/stats")
      .catch(
        () =>
          ({
            total: 0,
            open: 0,
            in_progress: 0,
            blocked: 0,
            done: 0,
            skipped: 0,
            blocking_go_live: 0,
            distinct_projects: 0,
            estimated_minutes_pending: 0,
          }) satisfies ResidualStatsResponse,
      ),
  ]);

  const minutesH = Math.floor(stats.estimated_minutes_pending / 60);
  const minutesM = stats.estimated_minutes_pending % 60;
  const minutesLabel =
    stats.estimated_minutes_pending === 0
      ? "—"
      : minutesH > 0
        ? `${minutesH}h ${minutesM}m`
        : `${minutesM}m`;

  const kpis: Kpi[] = [
    { label: "Total", value: stats.total },
    {
      label: "Abiertas",
      value: stats.open + stats.in_progress + stats.blocked,
      accent: (stats.open + stats.in_progress + stats.blocked) > 0,
    },
    {
      label: "Bloqueantes",
      value: stats.blocking_go_live,
      accent: stats.blocking_go_live > 0,
    },
    { label: "Proyectos", value: stats.distinct_projects },
    { label: "Tiempo pendiente", value: minutesLabel },
  ];

  const chips: FilterChip[] = STATUS_CHIPS_SOURCE.map(([value, label]) => ({
    id: `status:${value}`,
    label,
    count: stats[value as keyof ResidualStatsResponse] as number,
    param: "status",
    value,
  }));

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-lg font-semibold text-wcm-text">
          Tareas residuales
        </h1>
        <p className="text-xs text-muted-foreground">
          Trabajo manual pendiente repartido en proyectos. Las
          bloqueantes son las que impiden el go-live.
        </p>
      </header>

      <KpiStrip kpis={kpis} />

      <section className="space-y-3">
        <header className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            Listado
          </h2>
          <span className="text-[10.5px] tabular-nums text-muted-foreground">
            {`${tasks.length} resultado${tasks.length === 1 ? "" : "s"}`}
            {params.status
              ? ` · filtrado por ${STATUS_LABEL[params.status] ?? params.status}`
              : ""}
          </span>
        </header>
        {stats.total > 0 && <FilterChips chips={chips} />}
        {tasks.length === 0 ? (
          <EmptyResiduals
            hasFilter={!!params.status}
            systemEmpty={stats.total === 0}
          />
        ) : (
          <ResidualTasksTable tasks={tasks} />
        )}
      </section>
    </div>
  );
}

function EmptyResiduals({
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
          Sin tareas residuales
        </div>
        <p className="mt-2 text-sm text-wcm-text/80">
          No hay proyectos con tareas pendientes registradas.
        </p>
        <p className="mt-2 text-xs text-muted-foreground">
          Las tareas residuales aparecen al finalizar el pipeline de
          una migración — el agente{" "}
          <code className="text-wcm-text">checklist-generator</code>
          {" "}recopila lo que el operador debe terminar a mano (mover
          DNS, configurar Stripe, etc.).
        </p>
      </div>
    );
  }
  return (
    <div className="rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-6 text-center">
      <p className="text-sm text-wcm-text/70">
        {hasFilter
          ? "Sin tareas con este filtro de estado."
          : "Sin tareas en la página actual."}
      </p>
    </div>
  );
}
