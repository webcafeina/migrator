import Link from "next/link";

import { cn, formatRelativeTime } from "@/lib/utils";
import type { ResidualTaskRead } from "@/types/api";

import { MarkDoneButton } from "../mark-done-button";

interface ResidualTasksTableProps {
  tasks: ResidualTaskRead[];
  className?: string;
}

const CATEGORY_LABEL: Record<string, string> = {
  blocking_go_live: "bloqueante",
  client_config: "cliente",
  visual_content: "visual",
  post_go_live: "post-go-live",
  other: "otro",
};

/**
 * Tabla de tareas residuales para el rediseño de /residual-tasks
 * (vista global). Distinta del checklist por proyecto
 * (`/projects/[id]/checklist`) — aquí mezcla tareas de TODOS los
 * proyectos para que el operador vea su carga total de trabajo
 * residual.
 *
 * Columnas:
 * 1. PROYECTO — link a /projects/{id}, con #id en monospace.
 * 2. CATEGORÍA — etiqueta corta en castellano + color por urgencia
 *    (blocking_go_live destaca en ámbar).
 * 3. TÍTULO + descripción truncada.
 * 4. ASIGNAR — hint del campo `assignee_hint` (rol, no persona).
 * 5. MIN — estimación.
 * 6. STATUS — pill.
 * 7. ACCIÓN — botón "Done" (solo si status != done/skipped).
 *
 * Responsive: oculta asignar + min en estrecho; las críticas
 * (proyecto + categoría + título + status + acción) siempre visibles.
 */
export function ResidualTasksTable({
  tasks,
  className,
}: ResidualTasksTableProps) {
  if (tasks.length === 0) return null;

  return (
    <div
      className={cn(
        "overflow-hidden rounded-sm border border-wcm-detail/40",
        className,
      )}
    >
      <table className="w-full border-collapse text-[12.5px]">
        <thead className="bg-wcm-secondary/40">
          <tr>
            <Th width="80px">Proyecto</Th>
            <Th width="120px">Categoría</Th>
            <Th>Tarea</Th>
            <Th width="100px" hideUntil="md">
              Asignar
            </Th>
            <Th width="70px" hideUntil="md">
              Min
            </Th>
            <Th width="110px">Estado</Th>
            <Th width="80px">Acción</Th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((t) => (
            <Row key={t.id} task={t} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Row({ task }: { task: ResidualTaskRead }) {
  const closed = task.status === "done" || task.status === "skipped";
  return (
    <tr
      className={cn(
        "border-t border-wcm-detail/40 transition-colors hover:bg-wcm-secondary/30",
        closed && "opacity-60",
      )}
    >
      <td className="px-4 py-2.5">
        <Link
          href={`/projects/${task.project_id}`}
          className="tabular-nums text-wcm-text/70 hover:text-wcm-accent"
        >
          {`#${task.project_id}`}
        </Link>
      </td>
      <td className="px-4 py-2.5">
        <CategoryBadge value={task.category} />
      </td>
      <td className="px-4 py-2.5">
        <div className="font-medium text-wcm-text">{task.title}</div>
        {task.description && (
          <div className="mt-0.5 line-clamp-2 text-[11px] text-wcm-text/70">
            {task.description}
          </div>
        )}
        {task.closed_at && (
          <div className="mt-0.5 text-[10px] tabular-nums text-muted-foreground">
            {`cerrada ${formatRelativeTime(task.closed_at)}`}
          </div>
        )}
      </td>
      <td className="hidden px-4 py-2.5 text-[11.5px] text-wcm-text/70 md:table-cell">
        {task.assignee_hint ?? <span className="text-muted-foreground">—</span>}
      </td>
      <td className="hidden px-4 py-2.5 tabular-nums text-wcm-text/70 md:table-cell">
        {task.estimated_minutes != null ? (
          task.estimated_minutes
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </td>
      <td className="px-4 py-2.5">
        <StatusPill status={task.status} />
      </td>
      <td className="px-4 py-2.5">
        {!closed ? (
          <MarkDoneButton taskId={task.id} />
        ) : (
          <span className="text-[10.5px] text-muted-foreground">—</span>
        )}
      </td>
    </tr>
  );
}

function CategoryBadge({ value }: { value: string }) {
  const isBlocking = value === "blocking_go_live";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm border px-1.5 py-0.5 text-[10.5px] uppercase tracking-wider",
        isBlocking
          ? "border-wcm-warning/50 bg-wcm-warning/10 text-wcm-warning"
          : "border-wcm-detail/60 text-wcm-text/70",
      )}
    >
      {CATEGORY_LABEL[value] ?? value}
    </span>
  );
}

function StatusPill({ status }: { status: string }) {
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
        "inline-flex items-center rounded-sm border px-2 py-0.5 text-[10px] uppercase tracking-wider",
        spec.cls,
      )}
    >
      {spec.label}
    </span>
  );
}

function Th({
  children,
  width,
  hideUntil,
}: {
  children: React.ReactNode;
  width?: string;
  hideUntil?: "md" | "lg";
}) {
  const visibility =
    hideUntil === "lg"
      ? "hidden lg:table-cell"
      : hideUntil === "md"
        ? "hidden md:table-cell"
        : "";
  return (
    <th
      style={width ? { width } : undefined}
      className={cn(
        "px-4 py-2 text-left text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground",
        visibility,
      )}
    >
      {children}
    </th>
  );
}
