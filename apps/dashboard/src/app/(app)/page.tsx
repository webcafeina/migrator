import Link from "next/link";

import {
  FilterChips,
  type FilterChip,
} from "@/components/filter-chips";
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
import { KpiStrip, type Kpi } from "@/components/kpi-strip";

interface LeadStatsResponse {
  total: number;
  uncontacted: number;
  avg_score: number | null;
  distinct_builders: number;
  distinct_sectors: number;
  distinct_regions: number;
}

interface SearchParams {
  /** Filtro del feed por tipo de acción (audit_log.action). */
  action?: string;
}

const ACTION_CHIPS: FilterChip[] = [
  { id: "action:discover", label: "descubrir", param: "action", value: "discover" },
  { id: "action:fingerprint", label: "fingerprint", param: "action", value: "fingerprint" },
  { id: "action:enrich", label: "enriquecer", param: "action", value: "enrich" },
  { id: "action:send", label: "outreach", param: "action", value: "send" },
  { id: "action:opt_out", label: "opt-out", param: "action", value: "opt_out" },
  { id: "action:deploy", label: "deploy", param: "action", value: "deploy" },
  { id: "action:system", label: "sistema", param: "action", value: "system" },
];

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
export default async function OverviewPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
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
          searchParams: {
            limit: 50,
            ...(params.action ? { action: params.action } : {}),
          },
        })
        .catch(() => [] as AuditLogEntry[]),
    ]);

  // Sistema recién provisionado: 0 leads + 0 proyectos + 0 actividad.
  // Mostramos un onboarding card en lugar del feed vacío.
  const isEmptySystem =
    leadStats.total === 0 &&
    projectsActive.length === 0 &&
    auditLog.length === 0 &&
    !params.action;

  const kpis: Kpi[] = [
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

      <KpiStrip kpis={kpis} />

      {isEmptySystem ? (
        <OnboardingCard />
      ) : (
        <section className="space-y-3">
          <header className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
              Actividad reciente
            </h2>
            <span className="text-[10.5px] tabular-nums text-muted-foreground">
              {`${auditLog.length} eventos · últimos 7 días`}
              {params.action ? ` · filtrado por ${params.action}` : ""}
            </span>
          </header>
          <FilterChips chips={ACTION_CHIPS} />
          <ActivityFeed events={auditLog} />
        </section>
      )}
    </div>
  );
}

/**
 * Onboarding card que sustituye al feed cuando el sistema está recién
 * provisionado (0 leads, 0 proyectos, 0 eventos). Evita el "primer
 * impacto vacío" — el operador ve qué hacer a continuación.
 */
function OnboardingCard() {
  return (
    <div className="rounded-sm border border-wcm-accent/30 bg-wcm-accent/[0.04] p-8">
      <div className="text-[10.5px] font-semibold uppercase tracking-[0.1em] text-wcm-accent">
        Sistema recién provisionado
      </div>
      <h2 className="mt-3 text-base font-semibold text-wcm-text">
        Empieza por descubrir tus primeros leads.
      </h2>
      <p className="mt-2 max-w-2xl text-sm text-wcm-text/70">
        Lanza una campaña indicando sector y región para que el worker
        descubra empresas vía Google Places, las clasifique por tecnología
        (WordPress, Wix, Webflow, …) y las enriquezca con datos de
        contacto. La aprobación del outreach siempre es manual.
      </p>
      <div className="mt-5 flex flex-wrap gap-2">
        <Link
          href="/campaigns"
          className="rounded-sm bg-wcm-accent px-3.5 py-1.5 text-xs font-semibold text-wcm-primary hover:brightness-105"
        >
          + Lanzar primera campaña →
        </Link>
        <Link
          href="/settings"
          className="rounded-sm border border-wcm-detail/60 px-3.5 py-1.5 text-xs text-wcm-text/80 hover:border-muted-foreground hover:text-wcm-text"
        >
          Ver configuración del entorno
        </Link>
      </div>
    </div>
  );
}
