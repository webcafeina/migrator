import { notFound } from "next/navigation";

import { ApiError, api } from "@/lib/api";
import type { ProjectPhaseRead, ProjectRead } from "@/types/api";

import { ProjectActions } from "../actions";
import {
  ProjectHeader,
  type ProjectSummaryData,
} from "../_components/project-header";
import { ProjectPoller } from "../_components/project-poller";

import { PreviewPanel } from "./_components/preview-panel";

interface PreviewPageInfo {
  slug: string;
  title: string;
  intent: string | null;
  n_sections: number;
  bricks_page_id: number | null;
  wp_post_id: number | null;
  wp_post_status: string | null;
  last_regenerated_at: string | null;
}

interface PreviewResponse {
  project_id: number;
  project_status: string;
  design_method: string | null;
  brief: Record<string, unknown> | null;
  pages: PreviewPageInfo[];
}

/**
 * `/projects/[id]/preview` — revisión iterativa del rediseño (v0.25.1 B7).
 *
 * Server Component que fetcha el preview info + project + phases en
 * paralelo y los pasa al `<PreviewPanel>` cliente para interacción
 * (regenerar página, editar brief, aprobar+publicar).
 */
export default async function PreviewPage({
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

  const [summary, preview, phases] = await Promise.all([
    api
      .get<ProjectSummaryData>(`/api/v1/projects/${id}/summary`)
      .catch(() => emptySummary(project.id)),
    api.get<PreviewResponse>(`/api/v1/projects/${id}/preview`),
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

      <ProjectPoller status={project.status} projectId={project.id} />

      <PreviewPanel
        projectId={project.id}
        designMethod={preview.design_method}
        brief={preview.brief}
        pages={preview.pages}
        projectStatus={preview.project_status}
      />
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
    pages_with_many_unknowns: 0,
  };
}
