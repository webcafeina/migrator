import { Check, Circle, Loader2, SkipForward, X } from "lucide-react";

import { cn } from "@/lib/utils";
import type { ProjectPhaseRead } from "@/types/api";

interface PipelineStepperProps {
  phases: ProjectPhaseRead[];
  className?: string;
}

/**
 * Orden canónico de las 15 fases del pipeline + label castellano corto
 * para etiquetar bajo cada step. El componente solo muestra las fases que
 * existen en `phases[]` — las condicionales no invocadas (migrate_woo,
 * configure_wpml) simplemente no aparecen. Mantiene el orden incluso si
 * la BD devuelve filas desordenadas.
 *
 * Fuente: `apps/worker/src/wcm_worker/pipeline.py::_DEFAULT_PHASES`.
 */
const _PHASE_ORDER: Array<{ name: string; label: string; short: string }> = [
  { name: "scrape_origin", label: "Scraping del origen", short: "Scraping" },
  { name: "extract_content", label: "Extracción de contenido", short: "Contenido" },
  { name: "preserve_seo", label: "Preservación SEO + redirects", short: "SEO" },
  { name: "optimize_assets", label: "Optimización de assets (WebP, fonts)", short: "Assets" },
  { name: "detect_multilang", label: "Detección de idiomas", short: "Idiomas" },
  { name: "theme_styles", label: "Síntesis de Theme Styles (colores + tipografía)", short: "Theme" },
  { name: "transpile_bricks", label: "Transpilación a Bricks JSON", short: "Bricks" },
  { name: "deploy_wp", label: "Despliegue en WordPress destino", short: "Deploy WP" },
  { name: "migrate_woo", label: "Migración WooCommerce", short: "Woo" },
  { name: "configure_wpml", label: "Configuración WPML", short: "WPML" },
  { name: "rebuild_forms", label: "Recreación de formularios (Gravity Forms)", short: "Forms" },
  { name: "visual_diff", label: "Visual diff origen vs destino", short: "Visual" },
  { name: "qa", label: "QA — Lighthouse + W3C + links", short: "QA" },
  { name: "generate_checklist", label: "Generación del checklist (PDF)", short: "Checklist" },
  { name: "sync_clickup", label: "Sincronización con ClickUp", short: "ClickUp" },
  { name: "notify", label: "Notificación al operador", short: "Notify" },
];

type Variant = "completed" | "running" | "failed" | "skipped" | "pending";

/**
 * Stepper horizontal vivo del pipeline (v0.18.0).
 *
 * Sustituye/complementa a `ProjectPhasesTimeline` (que sigue disponible
 * en el overview para detalle). Aquí lo importante es ver de un vistazo
 * dónde está el pipeline AHORA. 15 segmentos con icon + número + label
 * corto. Color por status. Hover → tooltip con metadata.
 *
 * - Mobile: scroll horizontal con snap (un segmento ocupa ~80px).
 * - Desktop: ocupa todo el ancho disponible, cada segmento crece.
 *
 * Reactividad: este componente es presentacional puro. El "feeling
 * vivo" viene de `ProjectPoller` que dispara `router.refresh()` cada 2s.
 */
export function PipelineStepper({ phases, className }: PipelineStepperProps) {
  if (phases.length === 0) {
    return (
      <div
        className={cn(
          "rounded-sm border border-dashed border-wcm-detail/40 bg-wcm-secondary/20 px-3 py-2 text-[10.5px] text-muted-foreground",
          className,
        )}
      >
        Sin fases registradas. Pulsa <strong className="text-wcm-text">Start</strong> para
        arrancar el pipeline.
      </div>
    );
  }

  const byName = new Map(phases.map((p) => [p.phase_name, p]));

  return (
    <ol
      className={cn(
        "flex snap-x snap-mandatory gap-1 overflow-x-auto py-1",
        // Pequeño truco: cada step `flex-1 min-w-[68px]`; en mobile el
        // overflow scrollea y snap al centro evita que se vea cortado.
        className,
      )}
      aria-label="Estado del pipeline"
    >
      {_PHASE_ORDER.map((spec, idx) => {
        const phase = byName.get(spec.name);
        const variant = _variantOf(phase);
        return (
          <Step
            key={spec.name}
            number={idx + 1}
            spec={spec}
            phase={phase}
            variant={variant}
          />
        );
      })}
    </ol>
  );
}

function _variantOf(phase: ProjectPhaseRead | undefined): Variant {
  if (!phase) return "pending";
  switch (phase.status) {
    case "completed":
      return "completed";
    case "running":
      return "running";
    case "failed":
      return "failed";
    case "skipped":
      return "skipped";
    case "pending":
    default:
      return "pending";
  }
}

interface StepProps {
  number: number;
  spec: { name: string; label: string; short: string };
  phase: ProjectPhaseRead | undefined;
  variant: Variant;
}

function Step({ number, spec, phase, variant }: StepProps) {
  const Icon = _iconOf(variant);
  const { ring, fg, bg, label } = _styleOf(variant);

  const duration = _computeDuration(phase);
  const tooltip = _buildTooltip({ spec, phase, variant, duration });

  return (
    <li
      className="group relative flex min-w-[68px] flex-1 snap-center flex-col items-center gap-1"
      aria-label={`${number}. ${spec.label}`}
    >
      <div
        className={cn(
          "relative flex h-7 w-7 items-center justify-center rounded-full border-2",
          ring,
          bg,
          variant === "running" && "shadow-[0_0_0_4px_rgba(177,241,0,0.18)]",
        )}
      >
        <Icon
          className={cn(
            "h-3.5 w-3.5",
            fg,
            variant === "running" && "animate-spin",
          )}
          aria-hidden
        />
      </div>
      <span
        className={cn(
          "max-w-full truncate text-[9.5px] uppercase tracking-wider",
          variant === "pending" ? "text-muted-foreground" : "text-wcm-text/80",
          variant === "running" && "font-semibold text-wcm-accent",
        )}
        title={spec.short}
      >
        {spec.short}
      </span>
      <span className="sr-only">{label}</span>
      {/* Tooltip CSS-only on hover/focus. Posicionado abajo del step. */}
      <div
        role="tooltip"
        className="pointer-events-none absolute top-10 z-20 hidden w-56 -translate-x-1/2 rounded-sm border border-wcm-detail/60 bg-wcm-primary p-2 text-left text-[10.5px] text-wcm-text shadow-lg group-hover:block group-focus-within:block"
        style={{ left: "50%" }}
      >
        {tooltip}
      </div>
    </li>
  );
}

function _iconOf(variant: Variant) {
  switch (variant) {
    case "completed":
      return Check;
    case "running":
      return Loader2;
    case "failed":
      return X;
    case "skipped":
      return SkipForward;
    case "pending":
    default:
      return Circle;
  }
}

function _styleOf(variant: Variant): {
  ring: string;
  fg: string;
  bg: string;
  label: string;
} {
  switch (variant) {
    case "completed":
      return {
        ring: "border-wcm-accent/60",
        fg: "text-wcm-accent",
        bg: "bg-wcm-accent/15",
        label: "Completada",
      };
    case "running":
      return {
        ring: "border-wcm-accent",
        fg: "text-wcm-accent",
        bg: "bg-wcm-accent/20",
        label: "En ejecución",
      };
    case "failed":
      return {
        ring: "border-wcm-danger/60",
        fg: "text-wcm-danger",
        bg: "bg-wcm-danger/15",
        label: "Fallida",
      };
    case "skipped":
      return {
        ring: "border-wcm-warning/60",
        fg: "text-wcm-warning",
        bg: "bg-wcm-warning/10",
        label: "Saltada",
      };
    case "pending":
    default:
      return {
        ring: "border-wcm-detail/50",
        fg: "text-muted-foreground",
        bg: "bg-wcm-secondary/30",
        label: "Pendiente",
      };
  }
}

function _computeDuration(phase: ProjectPhaseRead | undefined): string | null {
  if (!phase?.started_at) return null;
  const start = new Date(phase.started_at).getTime();
  const end = phase.completed_at ? new Date(phase.completed_at).getTime() : Date.now();
  const sec = Math.max(0, Math.round((end - start) / 1000));
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}m ${s}s`;
}

function _buildTooltip({
  spec,
  phase,
  variant,
  duration,
}: {
  spec: { label: string };
  phase: ProjectPhaseRead | undefined;
  variant: Variant;
  duration: string | null;
}) {
  const summary =
    (phase?.output_summary as Record<string, unknown> | null)?.summary;
  const error = phase?.error_log;

  return (
    <>
      <div className="mb-1 font-semibold text-wcm-text">{spec.label}</div>
      <div className="text-muted-foreground">
        <span className={cn(_styleOf(variant).fg)}>
          {_styleOf(variant).label}
        </span>
        {duration && <span className="ml-2">· {duration}</span>}
        {phase?.attempt && phase.attempt > 1 && (
          <span className="ml-2">· intento {phase.attempt}</span>
        )}
      </div>
      {typeof summary === "string" && summary.length > 0 && (
        <div className="mt-1 text-wcm-text/80">
          {summary.length > 140 ? summary.slice(0, 140) + "…" : summary}
        </div>
      )}
      {error && (
        <div className="mt-1 break-words text-wcm-danger">
          {error.length > 160 ? error.slice(0, 160) + "…" : error}
        </div>
      )}
    </>
  );
}
