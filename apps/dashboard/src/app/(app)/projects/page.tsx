import Link from "next/link";

import { KpiStrip, type Kpi } from "@/components/kpi-strip";
import { api } from "@/lib/api";
import type { ProjectRead } from "@/types/api";

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
export default async function ProjectsPage() {
  const [projects, stats] = await Promise.all([
    api
      .get<ProjectRead[]>("/api/v1/projects")
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
  ]);

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
          href="/leads"
          className="rounded-sm bg-wcm-accent px-3 py-1.5 text-xs font-semibold text-wcm-primary hover:brightness-105"
          title="Los proyectos nacen de un lead cualificado — selecciona uno con score alto y convíertelo desde su ficha"
        >
          + Nuevo proyecto
        </Link>
      </header>

      <KpiStrip kpis={kpis} />

      <section className="space-y-3">
        <header className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            Listado
          </h2>
          <span className="text-[10.5px] tabular-nums text-muted-foreground">
            {`${projects.length} resultado${projects.length === 1 ? "" : "s"}`}
          </span>
        </header>
        {projects.length === 0 ? (
          <EmptyProjects />
        ) : (
          <ProjectsTable projects={projects} />
        )}
      </section>
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
