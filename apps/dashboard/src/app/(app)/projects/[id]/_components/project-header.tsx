import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { cn } from "@/lib/utils";
import type { ProjectPhaseRead, ProjectRead } from "@/types/api";

import { FeatureBadges } from "./feature-badges";
import { PhaseProgressBar } from "./phase-progress-bar";
import { ProjectTabs } from "./project-tabs";

export interface ProjectSummaryData {
  project_id: number;
  lead_origin: {
    id: number;
    business_name: string | null;
    score: number;
    builder_detected: string | null;
  } | null;
  phases_total: number;
  phases_completed: number;
  phases_failed: number;
  phases_running: number;
  phases_pending: number;
  current_phase_name: string | null;
  residual_total: number;
  residual_open: number;
  residual_done: number;
}

interface ProjectHeaderProps {
  project: ProjectRead;
  summary: ProjectSummaryData;
  /** Slot opcional para acciones de proyecto (start/resume/cancel). */
  actions?: React.ReactNode;
  /** v0.17.0 — si se pasa, pinta badges Woo/Forms/WPML según estado. */
  phases?: ProjectPhaseRead[];
  className?: string;
}

/**
 * Header común a las 4 sub-páginas de `/projects/[id]` (overview,
 * checklist, diff). Reemplaza la "isla de información" que cada
 * sub-página repetía con su propio breadcrumb y título.
 *
 * Estructura:
 * - Breadcrumb "← Proyectos" arriba (vuelta al listado).
 * - Identificación: cliente + #id + status badge + URL origen.
 * - PhaseProgressBar con counts globales.
 * - Línea densa "fase actual · residuales · diff · lead origen".
 * - Slot `actions` (botones start/resume/cancel) a la derecha del
 *   título.
 * - Tabs al final (Overview · Checklist · Visual diff).
 *
 * Presentacional puro. Los datos vienen del fetch de `page.tsx` (que
 * los hace en paralelo con `Promise.all`).
 */
export function ProjectHeader({
  project,
  summary,
  actions,
  phases,
  className,
}: ProjectHeaderProps) {
  const url = String(project.source_url);
  const displayUrl = url.replace(/^https?:\/\//i, "").replace(/\/$/, "");

  return (
    <header className={cn("flex flex-col gap-3", className)}>
      <Link
        href="/projects"
        className="inline-flex items-center gap-1 self-start text-[11px] text-muted-foreground hover:text-wcm-accent"
      >
        <ArrowLeft className="h-3 w-3" aria-hidden /> Proyectos
      </Link>

      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <div className="min-w-0">
          <div className="text-[10.5px] uppercase tracking-[0.08em] text-muted-foreground">
            {`Proyecto · #${project.id}`}
          </div>
          <h1 className="mt-1 truncate text-xl font-bold leading-tight text-wcm-text">
            {project.client_name}
          </h1>
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-1 inline-block text-xs text-wcm-text/70 hover:text-wcm-accent"
            title={url}
          >
            {`${displayUrl} ↗`}
          </a>
          {phases && (
            <FeatureBadges
              project={project}
              phases={phases}
              className="mt-2"
            />
          )}
        </div>
        {actions && <div className="shrink-0">{actions}</div>}
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_auto] md:items-center">
        <PhaseProgressBar
          total={summary.phases_total}
          completed={summary.phases_completed}
          failed={summary.phases_failed}
          running={summary.phases_running}
        />
        <MetaLine summary={summary} />
      </div>

      <ProjectTabs
        projectId={project.id}
        counts={{ residualOpen: summary.residual_open }}
      />
    </header>
  );
}

/**
 * Línea densa con la fase actual + counts de residuales + diff + lead.
 * Sustituye la "Configuración + Estado" en cards separadas de la
 * versión anterior por una sola fila escaneable.
 */
function MetaLine({ summary }: { summary: ProjectSummaryData }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
      {summary.current_phase_name && (
        <>
          <span>
            fase{" "}
            <strong className="font-semibold text-wcm-text">
              {summary.current_phase_name}
            </strong>
            {summary.phases_running > 0 && (
              <span className="ml-1 text-wcm-accent">· en curso</span>
            )}
          </span>
          <Sep />
        </>
      )}
      <span>
        residuales{" "}
        <strong
          className={cn(
            "font-semibold tabular-nums",
            summary.residual_open > 0 ? "text-wcm-warning" : "text-wcm-text",
          )}
        >
          {summary.residual_open}
        </strong>
        {summary.residual_total > 0 && (
          <span className="ml-0.5">{`/${summary.residual_total}`}</span>
        )}
      </span>
      {summary.lead_origin && (
        <>
          <Sep />
          <Link
            href={`/leads?selected=${summary.lead_origin.id}`}
            className="hover:text-wcm-accent"
          >
            {`lead origen · ${summary.lead_origin.business_name ?? `#${summary.lead_origin.id}`} (score ${summary.lead_origin.score})`}
          </Link>
        </>
      )}
    </div>
  );
}

function Sep() {
  return <span aria-hidden>·</span>;
}
