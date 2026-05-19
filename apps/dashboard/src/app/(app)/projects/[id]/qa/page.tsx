import { notFound } from "next/navigation";
import { Info } from "lucide-react";

import { ApiError, api } from "@/lib/api";
import type { ProjectPhaseRead, ProjectRead } from "@/types/api";

import { ProjectActions } from "../actions";
import {
  ProjectHeader,
  type ProjectSummaryData,
} from "../_components/project-header";
import { ProjectPoller } from "../_components/project-poller";

import { QaScorecards } from "./_components/qa-scorecards";

interface QaReportData {
  id: number;
  project_id: number;
  lighthouse_perf_desktop: number | null;
  lighthouse_perf_mobile: number | null;
  lighthouse_a11y_avg: number | null;
  lighthouse_best_practices_avg: number | null;
  lighthouse_seo_avg: number | null;
  html_validator_errors_count: number;
  html_validator_warnings_count: number;
  broken_links_count: number;
  total_links_checked: number;
  https_valid: boolean | null;
  robots_accessible: boolean | null;
  sitemap_accessible: boolean | null;
  report_json: {
    broken_links?: Array<{
      url: string;
      status_code: number | null;
      error: string | null;
      source_pages: string[];
    }>;
    lighthouse_skipped?: boolean;
    html_pages_validated?: number;
  } | null;
  created_at: string;
  updated_at: string;
}

/**
 * `/projects/[id]/qa` — reporte QA del último run del `qa-runner` (v0.16.0).
 *
 * Server Component que muestra scorecards Lighthouse + counters
 * HTML/links + checks binarios + lista detallada de broken links.
 * Sin reporte aún → placeholder explicativo.
 */
export default async function QaPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let project: ProjectRead;
  try {
    project = await api.get<ProjectRead>(`/api/v1/projects/${id}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  const [summary, report, phases] = await Promise.all([
    api
      .get<ProjectSummaryData>(`/api/v1/projects/${id}/summary`)
      .catch(() => emptySummary(project.id)),
    api
      .get<QaReportData | null>(`/api/v1/projects/${id}/qa-report`)
      .catch(() => null),
    api
      .get<ProjectPhaseRead[]>(`/api/v1/projects/${id}/phases`)
      .catch(() => [] as ProjectPhaseRead[]),
  ]);

  return (
    <div className="space-y-5">
      <ProjectHeader
        project={project}
        summary={summary}
        phases={phases}
        actions={
          <ProjectActions projectId={project.id} status={project.status} />
        }
      />

      <ProjectPoller status={project.status} />

      <section className="space-y-4">
        <header className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            QA · Lighthouse + W3C + links + SEO
          </h2>
          {report && (
            <span className="text-[10.5px] tabular-nums text-muted-foreground">
              {`última ejecución · `}
              <strong className="text-wcm-text">
                {new Date(report.created_at).toLocaleString("es-ES")}
              </strong>
            </span>
          )}
        </header>

        {report ? (
          <>
            <QaScorecards report={report} />
            {report.report_json?.broken_links &&
              report.report_json.broken_links.length > 0 && (
                <section className="space-y-2">
                  <h3 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
                    Links rotos detallados
                  </h3>
                  <div className="overflow-hidden rounded-sm border border-wcm-detail/40">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-wcm-detail/40 bg-wcm-secondary/30 text-[10.5px] uppercase tracking-wider text-muted-foreground">
                          <th className="px-3 py-2 text-left">URL rota</th>
                          <th className="px-3 py-2 text-left">Status</th>
                          <th className="px-3 py-2 text-left">
                            Aparece en
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {report.report_json.broken_links
                          .slice(0, 50)
                          .map((bl, idx) => (
                            <tr
                              key={idx}
                              className="border-b border-wcm-detail/20 last:border-b-0"
                            >
                              <td className="px-3 py-1.5 font-mono text-[11px] text-wcm-text">
                                {bl.url}
                              </td>
                              <td className="px-3 py-1.5 text-wcm-danger">
                                {bl.status_code ?? bl.error ?? "?"}
                              </td>
                              <td className="px-3 py-1.5 text-muted-foreground">
                                {bl.source_pages?.length ?? 0}{" "}
                                página(s)
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}
          </>
        ) : (
          <div className="flex items-start gap-3 rounded-sm border border-wcm-warning/30 bg-wcm-warning/[0.06] p-6 text-sm text-wcm-text/80">
            <Info
              className="h-5 w-5 shrink-0 text-wcm-warning"
              aria-hidden
            />
            <div className="space-y-2">
              <p>
                El proyecto aún no tiene reporte QA. Ejecuta el agente{" "}
                <code className="text-wcm-text">qa-runner</code> desde el
                pipeline para generar Lighthouse + validación HTML + links.
              </p>
              <p className="text-xs text-muted-foreground">
                Requiere <code>npm install -g lighthouse@^12</code> en el
                servidor del worker.
              </p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function emptySummary(projectId: number): ProjectSummaryData {
  return {
    project_id: projectId,
    lead_origin: null,
    phases_total: 0,
    phases_completed: 0,
    phases_failed: 0,
    phases_running: 0,
    phases_pending: 0,
    current_phase_name: null,
    residual_total: 0,
    residual_open: 0,
    residual_done: 0,
  };
}
