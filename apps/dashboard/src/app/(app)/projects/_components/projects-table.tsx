import Link from "next/link";

import { cn, formatRelativeTime, truncate } from "@/lib/utils";
import type { ProjectRead } from "@/types/api";

interface ProjectsTableProps {
  projects: ProjectRead[];
  className?: string;
}

/**
 * Tabla principal de proyectos para el rediseño de /projects.
 *
 * Columnas (ordenadas por importancia operativa):
 * 1. CLIENTE — el dato pivote. Click → /projects/{id}.
 * 2. ORIGEN — URL truncada con favicon implícito vía dominio.
 * 3. BUILDER — badge con el builder origen detectado.
 * 4. DESTINO — target_domain o "—" si pendiente.
 * 5. ESTADO — status badge en castellano.
 * 6. DIFF — visual_diff_avg_score como % (mini barra opcional).
 * 7. ACTIVIDAD — formatRelativeTime de updated_at.
 *
 * Responsive: oculta columnas secundarias en viewports estrechos via
 * `hideUntil="md" | "lg"` (mismo patrón que CampaignRunsTable).
 *
 * Presentacional puro: devuelve `null` con lista vacía — el padre
 * decide qué empty state mostrar.
 */
export function ProjectsTable({ projects, className }: ProjectsTableProps) {
  if (projects.length === 0) return null;

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
            <Th>Cliente</Th>
            <Th hideUntil="md">Origen</Th>
            <Th width="110px" hideUntil="md">
              Builder
            </Th>
            <Th width="180px" hideUntil="lg">
              Destino
            </Th>
            <Th width="140px">Estado</Th>
            <Th width="100px" hideUntil="lg">
              Diff
            </Th>
            <Th width="120px" hideUntil="md">
              Actividad
            </Th>
          </tr>
        </thead>
        <tbody>
          {projects.map((p) => (
            <Row key={p.id} project={p} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Row({ project }: { project: ProjectRead }) {
  return (
    <tr className="border-t border-wcm-detail/40 transition-colors hover:bg-wcm-secondary/30">
      <td className="px-4 py-2.5">
        <Link
          href={`/projects/${project.id}`}
          className="font-medium text-wcm-text hover:text-wcm-accent"
        >
          {project.client_name}
        </Link>
        <div className="mt-0.5 text-[10.5px] tabular-nums text-muted-foreground">
          {`#${project.id}`}
          {project.lead_id != null && (
            <>
              {" · "}
              <Link
                href={`/leads?selected=${project.lead_id}`}
                className="hover:text-wcm-accent"
              >
                {`lead #${project.lead_id}`}
              </Link>
            </>
          )}
        </div>
      </td>
      <td className="hidden px-4 py-2.5 text-wcm-text/70 md:table-cell">
        <a
          href={String(project.source_url)}
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-wcm-accent"
          title={String(project.source_url)}
        >
          {truncate(stripProtocol(String(project.source_url)), 38)} ↗
        </a>
      </td>
      <td className="hidden px-4 py-2.5 md:table-cell">
        <BuilderBadge value={project.builder_source} />
      </td>
      <td className="hidden px-4 py-2.5 text-wcm-text/70 lg:table-cell">
        {project.target_domain ?? (
          <span className="text-muted-foreground">—</span>
        )}
      </td>
      <td className="px-4 py-2.5">
        <StatusBadge status={project.status} />
      </td>
      <td className="hidden px-4 py-2.5 lg:table-cell">
        <DiffIndicator score={project.visual_diff_avg_score} />
      </td>
      <td className="hidden px-4 py-2.5 tabular-nums text-muted-foreground md:table-cell">
        {formatRelativeTime(project.updated_at)}
      </td>
    </tr>
  );
}

function BuilderBadge({ value }: { value: string | null | undefined }) {
  if (!value || value === "unknown") {
    return <span className="text-muted-foreground">—</span>;
  }
  return (
    <span className="inline-flex items-center rounded-sm border border-wcm-detail/60 px-2 py-0.5 text-[10.5px] uppercase tracking-wider text-wcm-text/80">
      {value}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; className: string }> = {
    queued: {
      label: "encolado",
      className: "border-wcm-detail/60 text-wcm-text/70",
    },
    running: {
      label: "en curso",
      className: "border-wcm-accent/50 bg-wcm-accent/10 text-wcm-accent",
    },
    blocked_human_input: {
      label: "bloqueado",
      className:
        "border-wcm-warning/50 bg-wcm-warning/10 text-wcm-warning",
    },
    qa_failed: {
      label: "QA fallido",
      className: "border-wcm-danger/40 text-wcm-danger",
    },
    completed: {
      label: "completado",
      className: "border-wcm-detail/60 text-wcm-text/80",
    },
    cancelled: {
      label: "cancelado",
      className: "border-wcm-detail/60 text-muted-foreground",
    },
  };
  const spec = map[status] ?? {
    label: status,
    className: "border-wcm-detail/60 text-wcm-text/70",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm border px-2 py-0.5 text-[10.5px] uppercase tracking-wider",
        spec.className,
      )}
    >
      {spec.label}
    </span>
  );
}

function DiffIndicator({ score }: { score: number | null | undefined }) {
  if (score == null) {
    return <span className="text-muted-foreground">—</span>;
  }
  const pct = Math.round(score * 100);
  // 85+ verde, 70-84 ámbar, <70 rojo. Umbral 0.85 viene de §13 CLAUDE.md
  // (criterio de éxito de visual diff).
  const good = pct >= 85;
  const warn = !good && pct >= 70;
  const colorClass = good
    ? "bg-[#5fc591]"
    : warn
      ? "bg-wcm-warning"
      : "bg-wcm-danger";
  const textClass = good
    ? "text-[#5fc591]"
    : warn
      ? "text-wcm-warning"
      : "text-wcm-danger";
  return (
    <div className="flex items-center gap-2">
      <div className="relative h-1.5 w-12 overflow-hidden rounded-[1px] bg-wcm-secondary">
        <div
          className={cn("absolute inset-y-0 left-0", colorClass)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={cn("tabular-nums text-[11.5px]", textClass)}>
        {`${pct}%`}
      </span>
    </div>
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

function stripProtocol(url: string): string {
  return url.replace(/^https?:\/\//i, "").replace(/\/$/, "");
}
