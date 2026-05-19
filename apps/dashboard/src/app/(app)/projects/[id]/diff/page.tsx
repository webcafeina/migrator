import { notFound } from "next/navigation";

import { ApiError, api } from "@/lib/api";
import type { ProjectPhaseRead, ProjectRead } from "@/types/api";

import { ProjectActions } from "../actions";
import {
  ProjectHeader,
  type ProjectSummaryData,
} from "../_components/project-header";
import { ProjectPoller } from "../_components/project-poller";

import { DiffGallery } from "./_components/diff-gallery";

interface VisualDiffsResponse {
  project_id: number;
  avg_score: number | null;
  pages_total: number;
  pages: Array<{
    id: number;
    project_id: number;
    page_path: string;
    source_screenshot_url: string | null;
    target_screenshot_url: string | null;
    overlay_url: string | null;
    score: number | null;
    viewport_width: number;
    created_at: string;
    updated_at: string;
  }>;
}

/**
 * `/projects/[id]/diff` — galería visual diff origen vs destino (v0.16.0).
 *
 * Server Component que fetcha los 3 datos en paralelo (project,
 * summary, visual_diffs) y los pasa al `<DiffGallery>` cliente para
 * interacción (modal full-size).
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

  const [summary, diffs, phases] = await Promise.all([
    api
      .get<ProjectSummaryData>(`/api/v1/projects/${id}/summary`)
      .catch(() => emptySummary(project.id)),
    api
      .get<VisualDiffsResponse>(`/api/v1/projects/${id}/visual-diffs`)
      .catch(() => emptyDiffs(project.id)),
    api
      .get<ProjectPhaseRead[]>(`/api/v1/projects/${id}/phases`)
      .catch(() => [] as ProjectPhaseRead[]),
  ]);

  const scorePct =
    diffs.avg_score != null ? Math.round(diffs.avg_score * 100) : null;

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

      <ProjectPoller status={project.status} projectId={project.id} />

      <section className="space-y-3">
        <header className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            Visual diff · {diffs.pages_total} página
            {diffs.pages_total === 1 ? "" : "s"}
          </h2>
          {scorePct != null && (
            <span className="text-[10.5px] tabular-nums text-muted-foreground">
              {`score medio · `}
              <strong className="text-wcm-text">{`${scorePct}%`}</strong>
            </span>
          )}
        </header>

        <DiffGallery pages={diffs.pages} />

        <p className="text-[10px] text-muted-foreground">
          Las páginas se comparan con <code>pixelmatch</code> (threshold
          0.15). Score ≥85% verde, 70-85% ámbar, &lt;70% rojo. Click en
          cualquier thumbnail abre la comparación full-size.
        </p>
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

function emptyDiffs(projectId: number): VisualDiffsResponse {
  return {
    project_id: projectId,
    avg_score: null,
    pages_total: 0,
    pages: [],
  };
}
