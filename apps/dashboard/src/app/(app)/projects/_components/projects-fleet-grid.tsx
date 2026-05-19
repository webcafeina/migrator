import Link from "next/link";
import { Globe, Languages, ShoppingCart } from "lucide-react";

import { cn } from "@/lib/utils";

export interface ProjectFleetItem {
  id: number;
  client_name: string;
  source_url: string;
  target_domain: string | null;
  builder_source: string | null;
  status: string;
  visual_diff_avg_score: number | null;
  has_ecommerce: boolean;
  is_multilang: boolean;
  started_at: string | null;
  phase_summary: Record<string, string>;
  current_phase_name: string | null;
}

interface ProjectsFleetGridProps {
  projects: ProjectFleetItem[];
  className?: string;
}

const BUCKETS: Array<{ key: string; label: string }> = [
  { key: "scrape", label: "Scrape" },
  { key: "transpile", label: "Bricks" },
  { key: "deploy", label: "Deploy" },
  { key: "qa", label: "QA" },
  { key: "notify", label: "Notify" },
];

/**
 * Vista fleet de proyectos (v0.19.0). Grid de tarjetas con mini-stepper
 * de 5 dots agregados (scrape/transpile/deploy/qa/notify) por proyecto.
 *
 * - Cliente + URL origen + target en cabecera.
 * - Mini-stepper de 5 dots con colores por status del bucket.
 * - Pills: ScoreBadge (visual diff), ProjectStatusPill, badges features.
 * - Click navega a /projects/[id].
 *
 * Complementa `ProjectsTable` (vista densa). El operador alterna desde
 * el toggle View en /projects.
 */
export function ProjectsFleetGrid({
  projects,
  className,
}: ProjectsFleetGridProps) {
  return (
    <ul
      className={cn(
        "grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3",
        className,
      )}
      aria-label="Fleet de proyectos"
    >
      {projects.map((p) => (
        <li key={p.id}>
          <ProjectCard project={p} />
        </li>
      ))}
    </ul>
  );
}

function ProjectCard({ project }: { project: ProjectFleetItem }) {
  const displayUrl = project.source_url
    .replace(/^https?:\/\//i, "")
    .replace(/\/$/, "");

  return (
    <Link
      href={`/projects/${project.id}`}
      className="group flex flex-col gap-3 rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-3 transition-colors hover:border-wcm-accent/60 hover:bg-wcm-secondary/50"
    >
      <header className="flex items-baseline justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-wcm-text">
            {project.client_name}
          </h3>
          <p className="truncate text-[10.5px] text-muted-foreground">
            {displayUrl}
          </p>
        </div>
        <StatusPill status={project.status} />
      </header>

      <MiniStepper phaseSummary={project.phase_summary} />

      <footer className="flex flex-wrap items-baseline justify-between gap-2 pt-1">
        <div className="flex flex-wrap gap-1.5">
          {project.has_ecommerce && (
            <FeaturePill
              icon={<ShoppingCart className="h-2.5 w-2.5" aria-hidden />}
              label="Woo"
            />
          )}
          {project.is_multilang && (
            <FeaturePill
              icon={<Languages className="h-2.5 w-2.5" aria-hidden />}
              label="WPML"
            />
          )}
          {project.builder_source && project.builder_source !== "unknown" && (
            <FeaturePill
              icon={<Globe className="h-2.5 w-2.5" aria-hidden />}
              label={project.builder_source}
            />
          )}
        </div>
        <DiffScoreBadge score={project.visual_diff_avg_score} />
      </footer>
    </Link>
  );
}

function MiniStepper({
  phaseSummary,
}: {
  phaseSummary: Record<string, string>;
}) {
  return (
    <ol className="flex items-center gap-1.5" aria-label="Progreso por bucket">
      {BUCKETS.map((b, idx) => {
        const status = phaseSummary[b.key] ?? "pending";
        const cls = _bucketClass(status);
        return (
          <li key={b.key} className="flex flex-1 items-center gap-1.5">
            <span
              className={cn(
                "h-3 w-3 shrink-0 rounded-full border-2",
                cls,
                status === "running" && "animate-pulse",
              )}
              aria-label={`${b.label}: ${status}`}
              title={`${b.label}: ${status}`}
            />
            {idx < BUCKETS.length - 1 && (
              <span
                aria-hidden
                className={cn(
                  "h-px flex-1",
                  _connectorClass(status, phaseSummary[BUCKETS[idx + 1]!.key] ?? "pending"),
                )}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}

function _bucketClass(status: string): string {
  switch (status) {
    case "completed":
      return "border-wcm-accent bg-wcm-accent";
    case "running":
      return "border-wcm-accent bg-wcm-accent/40 shadow-[0_0_0_3px_rgba(177,241,0,0.15)]";
    case "failed":
      return "border-wcm-danger bg-wcm-danger";
    case "skipped":
      return "border-wcm-warning bg-wcm-warning/40";
    case "pending":
    default:
      return "border-wcm-detail/60 bg-wcm-secondary";
  }
}

function _connectorClass(left: string, right: string): string {
  // El conector es lima si AMBAS partes están completed.
  if (left === "completed" && right === "completed") return "bg-wcm-accent/60";
  if (left === "completed" || left === "running") return "bg-wcm-accent/30";
  return "bg-wcm-detail/40";
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    queued: { label: "encolado", cls: "border-wcm-detail/60 text-muted-foreground" },
    running: { label: "en curso", cls: "border-wcm-accent/60 bg-wcm-accent/15 text-wcm-accent" },
    blocked_human_input: {
      label: "bloqueado",
      cls: "border-wcm-warning/60 bg-wcm-warning/10 text-wcm-warning",
    },
    qa_failed: { label: "QA falló", cls: "border-wcm-warning/60 bg-wcm-warning/10 text-wcm-warning" },
    completed: { label: "completado", cls: "border-wcm-accent/40 text-wcm-accent" },
    cancelled: { label: "cancelado", cls: "border-wcm-detail/60 text-muted-foreground" },
    rolled_back: { label: "revertido", cls: "border-wcm-danger/40 text-wcm-danger" },
  };
  const v = map[status] ?? { label: status, cls: "border-wcm-detail/60 text-muted-foreground" };
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-sm border px-1.5 py-0.5 text-[9.5px] uppercase tracking-wider",
        v.cls,
      )}
    >
      {v.label}
    </span>
  );
}

function DiffScoreBadge({ score }: { score: number | null }) {
  if (score == null) return <span className="text-[10px] text-muted-foreground">diff —</span>;
  const pct = Math.round(score * 100);
  const cls =
    score >= 0.85
      ? "text-wcm-accent"
      : score >= 0.7
        ? "text-wcm-warning"
        : "text-wcm-danger";
  return (
    <span className={cn("text-[10.5px] font-semibold tabular-nums", cls)}>
      diff {pct}%
    </span>
  );
}

function FeaturePill({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-0.5 rounded-sm border border-wcm-detail/40 px-1 py-px text-[9.5px] uppercase tracking-wider text-muted-foreground">
      {icon}
      {label}
    </span>
  );
}
