import { notFound } from "next/navigation";

import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ProjectPhaseRead, ProjectRead } from "@/types/api";

import { ProjectActions } from "./actions";
import {
  ProjectHeader,
  type ProjectSummaryData,
} from "./_components/project-header";
import { ProjectPhasesTimeline } from "./_components/project-phases-timeline";

/**
 * `/projects/[id]` — overview del proyecto con header compartido +
 * timeline de fases + bloque compacto de configuración técnica.
 *
 * Fetcha en paralelo project + summary + phases. summary alimenta el
 * header denso (counts de fases, residuales, lead origen) y phases
 * alimenta el timeline detallado.
 */
export default async function ProjectDetailPage({
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

  const [summary, phases] = await Promise.all([
    api
      .get<ProjectSummaryData>(`/api/v1/projects/${id}/summary`)
      .catch(() => emptySummary(project.id)),
    api
      .get<ProjectPhaseRead[]>(`/api/v1/projects/${id}/phases`)
      .catch(() => [] as ProjectPhaseRead[]),
  ]);

  return (
    <div className="space-y-5">
      <ProjectHeader
        project={project}
        summary={summary}
        actions={
          <ProjectActions projectId={project.id} status={project.status} />
        }
      />

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_280px]">
        <div className="space-y-3">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            Fases del pipeline
          </h2>
          <ProjectPhasesTimeline phases={phases} />
        </div>

        <aside className="space-y-3">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            Configuración técnica
          </h2>
          <ConfigPanel project={project} />
        </aside>
      </section>
    </div>
  );
}

function ConfigPanel({ project }: { project: ProjectRead }) {
  const rows: Array<[string, React.ReactNode]> = [
    ["destino", project.target_domain ?? "—"],
    ["builder", project.builder_source ?? "—"],
    ["e-commerce", boolBadge(project.has_ecommerce ?? false)],
    [
      "multilang",
      project.is_multilang
        ? (project.langs ?? []).join(", ") || "sí"
        : "no",
    ],
    ["assets", project.asset_storage ?? "—"],
    ["preserve paths", boolBadge(project.preserve_paths ?? false)],
  ];
  return (
    <dl className="grid grid-cols-[100px_1fr] gap-x-3 gap-y-2 rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-4 text-xs">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted-foreground">{k}</dt>
          <dd className="break-all text-wcm-text">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function boolBadge(v: boolean) {
  return (
    <span
      className={cn(
        "inline-flex rounded-sm border px-1.5 text-[10px] uppercase tracking-wider",
        v
          ? "border-wcm-accent/40 bg-wcm-accent/10 text-wcm-accent"
          : "border-wcm-detail/60 text-muted-foreground",
      )}
    >
      {v ? "sí" : "no"}
    </span>
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
