import { notFound } from "next/navigation";
import { GitCompare, Info } from "lucide-react";

import { ApiError, api } from "@/lib/api";
import type { ProjectRead } from "@/types/api";

import { ProjectActions } from "../actions";
import {
  ProjectHeader,
  type ProjectSummaryData,
} from "../_components/project-header";

/**
 * `/projects/[id]/diff` — placeholder consciente. La galería visual
 * diff origen vs destino sigue pendiente de implementación. Mientras,
 * mostramos el header coherente con las otras sub-páginas y una
 * tarjeta explicando el flujo previsto (sin la mentira "Fase 10" del
 * placeholder anterior — visual diff ya tiene infra en
 * `packages/visual-diff/`, falta solo conectarlo a esta UI).
 */
export default async function DiffPage({
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

  const summary = await api
    .get<ProjectSummaryData>(`/api/v1/projects/${id}/summary`)
    .catch(() => emptySummary(project.id));

  const scorePct =
    project.visual_diff_avg_score != null
      ? Math.round(project.visual_diff_avg_score * 100)
      : null;

  return (
    <div className="space-y-5">
      <ProjectHeader
        project={project}
        summary={summary}
        actions={
          <ProjectActions projectId={project.id} status={project.status} />
        }
      />

      <section className="space-y-3">
        <header className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            Visual diff
          </h2>
          {scorePct != null && (
            <span className="text-[10.5px] tabular-nums text-muted-foreground">
              {`score medio · `}
              <strong className="text-wcm-text">{`${scorePct}%`}</strong>
            </span>
          )}
        </header>

        <div className="rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-6">
          <div className="flex items-start gap-3">
            <GitCompare
              className="h-5 w-5 shrink-0 text-wcm-accent"
              aria-hidden
            />
            <div className="space-y-3 text-sm text-wcm-text/80">
              <p>
                La galería visual diff (origen vs destino con overlay de
                divergencias) está pendiente de conectar a esta UI. La
                infraestructura del worker ya existe en{" "}
                <code className="text-wcm-text">
                  packages/visual-diff/
                </code>
                .
              </p>
              <ol className="ml-4 list-decimal space-y-1 text-xs text-muted-foreground">
                <li>
                  <code className="text-wcm-text">VisualDiffAgent</code>
                  {" "}toma screenshots de origen y destino con Playwright
                  para cada página clave.
                </li>
                <li>
                  Aplica <code className="text-wcm-text">pixelmatch</code>
                  {" "}con threshold 0.85 (§13 CLAUDE.md) y genera 3
                  imágenes por página (source/target/overlay).
                </li>
                <li>
                  Sube los assets a R2 y persiste el score por página +
                  el agregado en{" "}
                  <code className="text-wcm-text">
                    projects.visual_diff_avg_score
                  </code>
                  .
                </li>
                <li>
                  Esta vista mostrará la galería con navegación entre
                  páginas, zoom y filtro por score &lt; threshold.
                </li>
              </ol>
              <p className="flex items-start gap-2 rounded-sm border border-wcm-warning/30 bg-wcm-warning/[0.06] p-3 text-xs text-wcm-warning">
                <Info className="h-3.5 w-3.5 shrink-0 translate-y-px" aria-hidden />
                Mientras tanto, el score agregado del proyecto se ve en
                la columna &quot;Diff&quot; del listado de proyectos y en
                el header de esta página.
              </p>
            </div>
          </div>
        </div>
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
