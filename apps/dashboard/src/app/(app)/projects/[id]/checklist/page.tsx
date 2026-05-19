import { notFound } from "next/navigation";

import { ApiError, api } from "@/lib/api";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { ProjectPhaseRead, ProjectRead, ResidualTaskRead } from "@/types/api";

import { ProjectActions } from "../actions";
import {
  ProjectHeader,
  type ProjectSummaryData,
} from "../_components/project-header";
import { ProjectPoller } from "../_components/project-poller";

/** Orden canónico de categorías por urgencia operativa (las bloqueantes
 *  primero, las post go-live al final). Coincide con el agrupamiento
 *  del checklist-generator agent. */
const CATEGORY_ORDER = [
  "blocking_go_live",
  "client_config",
  "visual_content",
  "post_go_live",
  "other",
] as const;

const CATEGORY_LABEL: Record<string, string> = {
  blocking_go_live: "Bloqueantes para go-live",
  client_config: "Configuración del cliente",
  visual_content: "Contenido visual",
  post_go_live: "Post go-live",
  other: "Otras",
};

/**
 * `/projects/[id]/checklist` — tareas residuales del proyecto agrupadas
 * por categoría con orden canónico (bloqueantes → post go-live).
 * Comparte `ProjectHeader` con las demás sub-páginas para mantener
 * coherencia de navegación.
 */
export default async function ChecklistPage({
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

  const [summary, tasks, phases] = await Promise.all([
    api
      .get<ProjectSummaryData>(`/api/v1/projects/${id}/summary`)
      .catch(() => emptySummary(project.id)),
    api
      .get<ResidualTaskRead[]>("/api/v1/residual-tasks", {
        searchParams: { project_id: id },
      })
      .catch(() => [] as ResidualTaskRead[]),
    api
      .get<ProjectPhaseRead[]>(`/api/v1/projects/${id}/phases`)
      .catch(() => [] as ProjectPhaseRead[]),
  ]);

  const byCategory: Record<string, ResidualTaskRead[]> = {};
  for (const t of tasks) {
    const k = t.category as string;
    (byCategory[k] ??= []).push(t);
  }

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

      <section className="space-y-3">
        <header className="flex flex-wrap items-baseline justify-between gap-2">
          <div className="flex flex-wrap items-baseline gap-3">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
              Checklist humano
            </h2>
            <span className="text-[10.5px] tabular-nums text-muted-foreground">
              {`${summary.residual_open} abiertas · ${summary.residual_done} cerradas · ${tasks.length} total`}
            </span>
          </div>
          {/* v0.16.0 — descarga del entregable PDF/MD del checklist
             generado por `checklist-generator`. Si el agent aún no
             ejecutó, los links devuelven 404 con mensaje claro. */}
          <div className="flex gap-2">
            <a
              href={`/api/v1/projects/${project.id}/checklist/download?format=pdf`}
              className="rounded-sm border border-wcm-accent/50 bg-wcm-accent/10 px-3 py-1 text-xs font-semibold text-wcm-accent hover:bg-wcm-accent/20"
              target="_blank"
              rel="noopener noreferrer"
            >
              Descargar PDF
            </a>
            <a
              href={`/api/v1/projects/${project.id}/checklist/download?format=md`}
              className="rounded-sm border border-wcm-detail/60 px-3 py-1 text-xs text-wcm-text/80 hover:border-wcm-detail hover:text-wcm-text"
              target="_blank"
              rel="noopener noreferrer"
            >
              MD
            </a>
          </div>
        </header>

        {tasks.length === 0 ? (
          <EmptyChecklist />
        ) : (
          <div className="flex flex-col gap-4">
            {CATEGORY_ORDER.map((cat) => {
              const items = byCategory[cat];
              if (!items || items.length === 0) return null;
              return (
                <CategoryGroup
                  key={cat}
                  label={CATEGORY_LABEL[cat] ?? cat}
                  category={cat}
                  items={items}
                />
              );
            })}
            {/* Categorías no canónicas (defensivo) */}
            {Object.entries(byCategory)
              .filter(([k]) => !CATEGORY_ORDER.includes(k as (typeof CATEGORY_ORDER)[number]))
              .map(([k, items]) => (
                <CategoryGroup
                  key={k}
                  label={CATEGORY_LABEL[k] ?? k}
                  category={k}
                  items={items}
                />
              ))}
          </div>
        )}
      </section>
    </div>
  );
}

function CategoryGroup({
  label,
  category,
  items,
}: {
  label: string;
  category: string;
  items: ResidualTaskRead[];
}) {
  const isBlocking = category === "blocking_go_live";
  return (
    <section
      className={cn(
        "rounded-sm border bg-wcm-secondary/30",
        isBlocking
          ? "border-wcm-warning/40"
          : "border-wcm-detail/40",
      )}
    >
      <header className="flex items-baseline gap-2 border-b border-wcm-detail/40 px-4 py-2">
        <h3
          className={cn(
            "text-[11px] font-semibold uppercase tracking-[0.08em]",
            isBlocking ? "text-wcm-warning" : "text-wcm-text/80",
          )}
        >
          {label}
        </h3>
        <span className="tabular-nums text-[10.5px] text-muted-foreground">
          {items.length}
        </span>
      </header>
      <ul className="divide-y divide-wcm-detail/40">
        {items.map((t) => (
          <TaskItem key={t.id} task={t} />
        ))}
      </ul>
    </section>
  );
}

function TaskItem({ task }: { task: ResidualTaskRead }) {
  return (
    <li className="px-4 py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-[13px] font-medium text-wcm-text">
          {task.title}
        </span>
        <TaskStatusPill status={task.status} />
      </div>
      {task.description && (
        <p className="mt-1 whitespace-pre-wrap text-[12px] text-wcm-text/70">
          {task.description}
        </p>
      )}
      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[10.5px] uppercase tracking-wider text-muted-foreground">
        {task.estimated_minutes != null && (
          <span>{`${task.estimated_minutes} min est.`}</span>
        )}
        {task.assignee_hint && <span>{`asignar · ${task.assignee_hint}`}</span>}
        {task.generated_by && <span>{`por ${task.generated_by}`}</span>}
        {task.closed_at && (
          <span>{`cerrada ${formatRelativeTime(task.closed_at)}`}</span>
        )}
      </div>
    </li>
  );
}

function TaskStatusPill({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    open: { label: "abierta", cls: "border-wcm-detail/60 text-wcm-text/80" },
    in_progress: {
      label: "en curso",
      cls: "border-wcm-accent/50 bg-wcm-accent/10 text-wcm-accent",
    },
    blocked: {
      label: "bloqueada",
      cls: "border-wcm-warning/50 bg-wcm-warning/10 text-wcm-warning",
    },
    done: {
      label: "cerrada",
      cls: "border-wcm-detail/60 text-muted-foreground",
    },
    skipped: {
      label: "omitida",
      cls: "border-wcm-detail/60 text-muted-foreground",
    },
  };
  const spec = map[status] ?? {
    label: status,
    cls: "border-wcm-detail/60 text-muted-foreground",
  };
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-sm border px-1.5 py-px text-[10px] uppercase tracking-wider",
        spec.cls,
      )}
    >
      {spec.label}
    </span>
  );
}

function EmptyChecklist() {
  return (
    <div className="rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-6 text-center">
      <p className="text-sm text-wcm-text/70">
        Sin tareas residuales registradas todavía.
      </p>
      <p className="mt-2 text-xs text-muted-foreground">
        Aparecen al finalizar el pipeline: el agente
        {" "}
        <code className="text-wcm-text">checklist-generator</code> recopila
        lo que el operador debe terminar a mano (mover DNS, configurar
        Stripe, etc.).
      </p>
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
