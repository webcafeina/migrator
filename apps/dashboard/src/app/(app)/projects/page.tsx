import Link from "next/link";
import { LayoutGrid, List } from "lucide-react";

import { FilterChips, type FilterChip } from "@/components/filter-chips";
import { KpiStrip, type Kpi } from "@/components/kpi-strip";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ProjectRead } from "@/types/api";

import {
  ProjectsFleetGrid,
  type ProjectFleetItem,
} from "./_components/projects-fleet-grid";
import { ProjectsTable } from "./_components/projects-table";

interface ProjectStatsResponse {
  total: number;
  queued: number;
  running: number;
  blocked: number;
  completed: number;
  failed_or_cancelled: number;
  distinct_builders: number;
  avg_visual_diff_score: number | null;
}

interface SearchParams {
  /** Filtro del listado por estado (project_status del API). */
  status?: string;
  /** v0.19.0 — toggle entre vistas. `fleet` = grid de tarjetas con
   *  mini-stepper; `table` (default) = tabla densa actual. */
  view?: "fleet" | "table";
}

/** Etiquetas castellanas para los chips de filtro. Coinciden con el
 *  copy de los status badges de `ProjectsTable` para que el operador
 *  reconozca el vocabulario al instante. */
const STATUS_LABEL: Record<string, string> = {
  queued: "encolados",
  running: "en curso",
  blocked_human_input: "bloqueados",
  qa_failed: "QA fallido",
  completed: "completados",
  cancelled: "cancelados",
};

/**
 * `/projects` — rediseño consistente con /leads, /campaigns y /:
 *
 * - Header con título + acción primaria "+ Nuevo proyecto" que enlaza
 *   a /leads (los proyectos nacen siempre de un lead cualificado).
 * - `KpiStrip` con 5 KPIs: total · en curso · bloqueados · completados ·
 *   diff medio.
 * - `ProjectsTable` con el listado, o `EmptyProjects` cuando 0.
 *
 * Server Component: 2 fetches en paralelo (lista + stats). `.catch()`
 * defensivo en ambos.
 */
export default async function ProjectsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const view: "fleet" | "table" = params.view === "fleet" ? "fleet" : "table";
  // En vista fleet fetcha el endpoint enriquecido /projects/fleet
  // (con phase_summary pre-agregada); en table mantiene el list+stats
  // ya existente.
  const [projects, stats, fleet] = await Promise.all([
    api
      .get<ProjectRead[]>("/api/v1/projects", {
        searchParams: params.status ? { project_status: params.status } : {},
      })
      .catch(() => [] as ProjectRead[]),
    api
      .get<ProjectStatsResponse>("/api/v1/projects/stats")
      .catch(
        () =>
          ({
            total: 0,
            queued: 0,
            running: 0,
            blocked: 0,
            completed: 0,
            failed_or_cancelled: 0,
            distinct_builders: 0,
            avg_visual_diff_score: null,
          }) satisfies ProjectStatsResponse,
      ),
    view === "fleet"
      ? api
          .get<ProjectFleetItem[]>("/api/v1/projects/fleet")
          .catch(() => [] as ProjectFleetItem[])
      : Promise.resolve([] as ProjectFleetItem[]),
  ]);
  // Filtro client-side por status en la vista fleet (el endpoint
  // devuelve todos; el listado base ya filtra server-side).
  const fleetFiltered = params.status
    ? fleet.filter((f) => f.status === params.status)
    : fleet;

  const kpis: Kpi[] = [
    { label: "Proyectos", value: stats.total },
    { label: "En curso", value: stats.running },
    {
      label: "Bloqueados",
      value: stats.blocked,
      accent: stats.blocked > 0,
    },
    { label: "Completados", value: stats.completed },
    {
      label: "Diff medio",
      value:
        stats.avg_visual_diff_score != null
          ? `${Math.round(stats.avg_visual_diff_score * 100)}%`
          : "—",
    },
  ];

  return (
    <div className="space-y-5">
      <header className="flex items-baseline justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold text-wcm-text">Proyectos</h1>
          <p className="text-xs text-muted-foreground">
            Migraciones de web origen → WordPress + Bricks. Estado por
            fase, visual diff y tareas residuales.
          </p>
        </div>
        <Link
          href="/projects/new"
          className="rounded-sm bg-wcm-accent px-3 py-1.5 text-xs font-semibold text-wcm-primary hover:brightness-105"
        >
          + Nuevo proyecto
        </Link>
      </header>

      <KpiStrip kpis={kpis} />

      <section className="space-y-3">
        <header className="flex flex-wrap items-baseline justify-between gap-2">
          <div className="flex items-baseline gap-3">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
              Listado
            </h2>
            <span className="text-[10.5px] tabular-nums text-muted-foreground">
              {view === "fleet"
                ? `${fleetFiltered.length} resultado${fleetFiltered.length === 1 ? "" : "s"}`
                : `${projects.length} resultado${projects.length === 1 ? "" : "s"}`}
              {params.status
                ? ` · filtrado por ${STATUS_LABEL[params.status] ?? params.status}`
                : ""}
            </span>
          </div>
          {/* v0.19.0 — toggle entre vista fleet (grid) y tabla densa. */}
          <ViewToggle activeView={view} activeStatus={params.status ?? null} />
        </header>
        {stats.total > 0 && (
          <FilterChips chips={buildStatusChips(stats)} />
        )}
        {(view === "fleet" ? fleetFiltered.length : projects.length) === 0 ? (
          stats.total === 0 ? (
            <EmptyProjects />
          ) : (
            <EmptyFilterResult activeStatus={params.status ?? null} />
          )
        ) : view === "fleet" ? (
          <ProjectsFleetGrid projects={fleetFiltered} />
        ) : (
          <ProjectsTable projects={projects} />
        )}
      </section>
    </div>
  );
}

/**
 * Construye los 5 chips de filtro a partir de los stats agregados
 * (no del listado actual — los counts deben ser globales para que el
 * operador vea cuántos hay en cada estado antes de filtrar).
 */
function buildStatusChips(stats: ProjectStatsResponse): FilterChip[] {
  return [
    {
      id: "status:queued",
      label: STATUS_LABEL.queued!,
      count: stats.queued,
      param: "status",
      value: "queued",
    },
    {
      id: "status:running",
      label: STATUS_LABEL.running!,
      count: stats.running,
      param: "status",
      value: "running",
    },
    {
      id: "status:blocked_human_input",
      label: STATUS_LABEL.blocked_human_input!,
      count: stats.blocked,
      param: "status",
      value: "blocked_human_input",
    },
    {
      id: "status:completed",
      label: STATUS_LABEL.completed!,
      count: stats.completed,
      param: "status",
      value: "completed",
    },
    // `failed_or_cancelled` es agregado en stats; el chip filtra por
    // cancelled (el más común); qa_failed se filtraría con otro chip
    // si se necesita en futuro.
    {
      id: "status:cancelled",
      label: STATUS_LABEL.cancelled!,
      count: stats.failed_or_cancelled,
      param: "status",
      value: "cancelled",
    },
  ];
}

/**
 * Toggle visual entre vista fleet (grid de tarjetas con mini-stepper)
 * y vista tabla densa (v0.19.0).
 *
 * Preserva el filtro `status` actual al cambiar de vista.
 */
function ViewToggle({
  activeView,
  activeStatus,
}: {
  activeView: "fleet" | "table";
  activeStatus: string | null;
}) {
  const baseParams = activeStatus ? `&status=${encodeURIComponent(activeStatus)}` : "";
  return (
    <div
      role="group"
      aria-label="Cambiar vista"
      className="inline-flex rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30"
    >
      <Link
        href={`/projects?view=table${baseParams}`}
        aria-current={activeView === "table" ? "true" : undefined}
        className={cn(
          "inline-flex items-center gap-1 px-2 py-1 text-[10.5px] uppercase tracking-wider",
          activeView === "table"
            ? "bg-wcm-accent/15 text-wcm-accent"
            : "text-muted-foreground hover:text-wcm-text",
        )}
      >
        <List className="h-3 w-3" aria-hidden />
        Tabla
      </Link>
      <Link
        href={`/projects?view=fleet${baseParams}`}
        aria-current={activeView === "fleet" ? "true" : undefined}
        className={cn(
          "inline-flex items-center gap-1 px-2 py-1 text-[10.5px] uppercase tracking-wider",
          activeView === "fleet"
            ? "bg-wcm-accent/15 text-wcm-accent"
            : "text-muted-foreground hover:text-wcm-text",
        )}
      >
        <LayoutGrid className="h-3 w-3" aria-hidden />
        Fleet
      </Link>
    </div>
  );
}


/**
 * Empty state cuando hay proyectos en el sistema pero el filtro actual
 * deja 0. Distinto de `EmptyProjects` (sistema sin proyectos).
 */
function EmptyFilterResult({ activeStatus }: { activeStatus: string | null }) {
  const label =
    activeStatus && STATUS_LABEL[activeStatus]
      ? STATUS_LABEL[activeStatus]
      : activeStatus ?? "—";
  return (
    <div className="rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-6 text-center">
      <p className="text-sm text-wcm-text/70">
        {`Sin proyectos en estado "${label}".`}
      </p>
      <p className="mt-2 text-xs text-muted-foreground">
        Quita el filtro arriba para ver todos, o lanza un nuevo proyecto
        desde un lead.
      </p>
    </div>
  );
}

/**
 * Empty state cuando aún no hay proyectos. Refuerza el modelo mental:
 * los proyectos nacen de un lead cualificado, no se crean en seco. 2
 * CTAs: ir a /leads (recomendado), o ver actividad del Panel.
 */
function EmptyProjects() {
  return (
    <div className="rounded-sm border border-wcm-accent/30 bg-wcm-accent/[0.04] p-8">
      <div className="text-[10.5px] font-semibold uppercase tracking-[0.1em] text-wcm-accent">
        Sin proyectos todavía
      </div>
      <h2 className="mt-3 text-base font-semibold text-wcm-text">
        Convierte un lead cualificado en migración.
      </h2>
      <p className="mt-2 max-w-2xl text-sm text-wcm-text/70">
        Los proyectos nacen siempre de un lead — el lead aporta la URL
        origen, el builder detectado, los contactos y el score. Desde la
        ficha del lead, &quot;Convertir a proyecto&quot; arranca el
        pipeline: scrape → bricks → deploy WP → visual diff → checklist
        residual.
      </p>
      <div className="mt-5 flex flex-wrap gap-2">
        <Link
          href="/leads"
          className="rounded-sm bg-wcm-accent px-3.5 py-1.5 text-xs font-semibold text-wcm-primary hover:brightness-105"
        >
          Ir a leads →
        </Link>
        <Link
          href="/"
          className="rounded-sm border border-wcm-detail/60 px-3.5 py-1.5 text-xs text-wcm-text/80 hover:border-muted-foreground hover:text-wcm-text"
        >
          Ver actividad del Panel
        </Link>
      </div>
    </div>
  );
}
