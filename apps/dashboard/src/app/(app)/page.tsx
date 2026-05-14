import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, statusVariant } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { statusLabel } from "@/lib/labels";
import { formatDate } from "@/lib/utils";
import type { ErrorLogRead, ProjectRead, ResidualTaskRead } from "@/types/api";

interface CountResponse {
  total: number;
}

async function fetchAll() {
  const [leadsCount, projectsActive, residualOpen, recentErrors] = await Promise.all([
    api.get<CountResponse>("/api/v1/leads/count").catch(() => ({ total: 0 })),
    api
      .get<ProjectRead[]>("/api/v1/projects", { searchParams: { project_status: "running" } })
      .catch(() => [] as ProjectRead[]),
    api
      .get<ResidualTaskRead[]>("/api/v1/residual-tasks", { searchParams: { status_filter: "open" } })
      .catch(() => [] as ResidualTaskRead[]),
    api
      .get<ErrorLogRead[]>("/api/v1/errors", { searchParams: { limit: 5 } })
      .catch(() => [] as ErrorLogRead[]),
  ]);
  return { leadsCount, projectsActive, residualOpen, recentErrors };
}

export default async function OverviewPage() {
  const { leadsCount, projectsActive, residualOpen, recentErrors } = await fetchAll();

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between">
        <h1 className="text-lg font-semibold text-wcm-text">Overview</h1>
        <span className="text-xs text-wcm-detail uppercase tracking-wider">
          Estado del sistema
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Leads totales" value={leadsCount.total} href="/leads" />
        <MetricCard
          label="Proyectos activos"
          value={projectsActive.length}
          href="/projects"
        />
        <MetricCard
          label="Tareas residuales abiertas"
          value={residualOpen.length}
          href="/residual-tasks"
        />
        <MetricCard
          label="Errores recientes (24h)"
          value={recentErrors.length}
          href="/errors"
          accent={recentErrors.length > 0}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Proyectos en ejecución</CardTitle>
        </CardHeader>
        <CardContent>
          {projectsActive.length === 0 ? (
            <p className="text-sm text-wcm-detail">
              Ningún proyecto en ejecución actualmente.
            </p>
          ) : (
            <ul className="space-y-2">
              {projectsActive.slice(0, 8).map((p) => (
                <li key={p.id} className="flex items-center justify-between text-sm">
                  <Link
                    href={`/projects/${p.id}`}
                    className="hover:text-wcm-accent"
                  >
                    #{p.id} {p.client_name}{" "}
                    <span className="text-wcm-detail">— {p.source_url}</span>
                  </Link>
                  <Badge variant={statusVariant(p.status)}>{statusLabel(p.status)}</Badge>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Errores recientes</CardTitle>
        </CardHeader>
        <CardContent>
          {recentErrors.length === 0 ? (
            <p className="text-sm text-wcm-detail">Sin errores recientes.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {recentErrors.map((e) => (
                <li key={e.id} className="flex items-baseline justify-between gap-3">
                  <span className="text-wcm-text truncate">
                    [{e.component}] {e.message}
                  </span>
                  <span className="shrink-0 text-xs text-wcm-detail">
                    {formatDate(e.at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function MetricCard({
  label,
  value,
  href,
  accent = false,
}: {
  label: string;
  value: number;
  href: string;
  accent?: boolean;
}) {
  return (
    <Link href={href} className="block group">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle>{label}</CardTitle>
          <ArrowUpRight className="h-4 w-4 text-wcm-detail group-hover:text-wcm-accent" />
        </CardHeader>
        <CardContent>
          <div
            className={`text-3xl font-semibold tabular-nums ${
              accent ? "text-wcm-warning" : "text-wcm-accent"
            }`}
          >
            {value}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
