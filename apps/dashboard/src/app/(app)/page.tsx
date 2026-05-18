import Link from "next/link";

import { api } from "@/lib/api";
import type {
  ErrorLogRead,
  ProjectRead,
  ResidualTaskRead,
} from "@/types/api";

import {
  ActivityFeed,
  type AuditLogEntry,
} from "./_overview/activity-feed";
import {
  OverviewKpiStrip,
  type OverviewKpi,
} from "./_overview/overview-kpi-strip";

interface LeadStatsResponse {
  total: number;
  uncontacted: number;
  avg_score: number | null;
  distinct_builders: number;
  distinct_sectors: number;
  distinct_regions: number;
}

/**
 * Panel/Overview — primera pantalla tras login.
 *
 * Layout: header con título + acciones rápidas, tira de KPIs en línea
 * (sustituye las 4 cards gigantes del Overview anterior), y feed central
 * con la actividad reciente del sistema agrupada por día.
 *
 * Server Component: 5 fetches en paralelo (stats leads, proyectos activos,
 * residuales abiertas, errores recientes, audit-log). Todos con
 * `.catch()` defensivo — si una pieza falla, las otras siguen
 * renderizando.
 */
export default async function OverviewPage() {
  const [leadStats, projectsActive, residualOpen, recentErrors, auditLog] =
    await Promise.all([
      api
        .get<LeadStatsResponse>("/api/v1/leads/stats")
        .catch(
          () =>
            ({
              total: 0,
              uncontacted: 0,
              avg_score: null,
              distinct_builders: 0,
              distinct_sectors: 0,
              distinct_regions: 0,
            }) satisfies LeadStatsResponse,
        ),
      api
        .get<ProjectRead[]>("/api/v1/projects", {
          searchParams: { project_status: "running" },
        })
        .catch(() => [] as ProjectRead[]),
      api
        .get<ResidualTaskRead[]>("/api/v1/residual-tasks", {
          searchParams: { status_filter: "open" },
        })
        .catch(() => [] as ResidualTaskRead[]),
      api
        .get<ErrorLogRead[]>("/api/v1/errors", { searchParams: { limit: 5 } })
        .catch(() => [] as ErrorLogRead[]),
      api
        .get<AuditLogEntry[]>("/api/v1/audit-log", {
          searchParams: { limit: 50 },
        })
        .catch(() => [] as AuditLogEntry[]),
    ]);

  const kpis: OverviewKpi[] = [
    {
      label: "Leads totales",
      value: leadStats.total,
      href: "/leads",
    },
    {
      label: "Sin contactar",
      value: leadStats.uncontacted,
      href: "/leads",
    },
    {
      label: "Proyectos activos",
      value: projectsActive.length,
      href: "/projects",
    },
    {
      label: "Tareas pendientes",
      value: residualOpen.length,
      href: "/residual-tasks",
    },
    {
      label: "Errores (24h)",
      value: recentErrors.length,
      href: "/errors",
      accent: recentErrors.length > 0,
    },
  ];

  return (
    <div className="space-y-5">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-lg font-semibold text-wcm-text">Panel</h1>
          <p className="text-xs text-muted-foreground">
            Estado del sistema y actividad reciente.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/campaigns"
            className="rounded-sm bg-wcm-accent px-3 py-1.5 text-xs font-semibold text-wcm-primary hover:brightness-105"
          >
            + Lanzar campaña
          </Link>
        </div>
      </header>

      <OverviewKpiStrip kpis={kpis} />

      <section className="space-y-3">
        <header className="flex items-baseline justify-between">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            Actividad reciente
          </h2>
          <span className="text-[10.5px] tabular-nums text-muted-foreground">
            {`${auditLog.length} eventos · últimos 7 días`}
          </span>
        </header>
        <ActivityFeed events={auditLog} />
      </section>
    </div>
  );
}
