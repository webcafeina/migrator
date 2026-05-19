import Link from "next/link";
import { Languages, ShoppingCart, SquarePen } from "lucide-react";

import { cn } from "@/lib/utils";
import type { ProjectPhaseRead, ProjectRead } from "@/types/api";

interface FeatureBadgesProps {
  project: ProjectRead;
  phases: ProjectPhaseRead[];
  className?: string;
}

type Variant = "active" | "pending" | "skipped" | "failed";

interface FeatureSpec {
  label: string;
  Icon: typeof ShoppingCart;
  phaseName: string;
  /** Si el agente generated_by que quiero linkar en residuales. */
  generatedBy: string;
  /** Si false, el badge NO se muestra (proyecto no aplica esta feature). */
  applies: boolean;
}

/**
 * Badges Woo / Forms / WPML (v0.17.0).
 *
 * Cada feature solo se muestra si el proyecto la activa:
 * - WooCommerce → project.has_ecommerce.
 * - Gravity Forms → siempre que la fase `rebuild_forms` haya ejecutado
 *   (positivo o negativo — refleja que el detector intentó).
 * - WPML → project.is_multilang.
 *
 * Color por estado de la fase:
 * - active (lima) → completed.
 * - pending (gris) → not started.
 * - skipped (ámbar) → completed con residual.
 * - failed (rojo) → failed.
 *
 * Click navega a /residual-tasks filtrado por `generated_by` del agente
 * para que el operador vea exactamente qué acciones manuales quedan.
 */
export function FeatureBadges({
  project,
  phases,
  className,
}: FeatureBadgesProps) {
  const phaseByName = new Map(phases.map((p) => [p.phase_name, p]));

  const features: FeatureSpec[] = [
    {
      label: "WooCommerce",
      Icon: ShoppingCart,
      phaseName: "migrate_woo",
      generatedBy: "woo-migrator",
      applies: Boolean(project.has_ecommerce),
    },
    {
      label: "Gravity Forms",
      Icon: SquarePen,
      phaseName: "rebuild_forms",
      generatedBy: "forms-rebuilder",
      // Forms-rebuilder corre siempre; solo lo mostramos si la fase
      // ya intentó (existe en phases con cualquier status final).
      applies: phaseByName.has("rebuild_forms"),
    },
    {
      label: "WPML",
      Icon: Languages,
      phaseName: "configure_wpml",
      generatedBy: "wpml-configurator",
      applies: Boolean(project.is_multilang),
    },
  ];

  const visible = features.filter((f) => f.applies);
  if (visible.length === 0) return null;

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-1.5",
        className,
      )}
      aria-label="Features del proyecto"
    >
      {visible.map((f) => {
        const phase = phaseByName.get(f.phaseName);
        const variant = _variantOf(phase);
        return (
          <Badge
            key={f.label}
            label={f.label}
            Icon={f.Icon}
            variant={variant}
            phaseSummary={phase?.output_summary as Record<string, unknown> | null | undefined}
            generatedBy={f.generatedBy}
          />
        );
      })}
    </div>
  );
}

function _variantOf(phase: ProjectPhaseRead | undefined): Variant {
  if (!phase) return "pending";
  switch (phase.status) {
    case "completed":
      // Si el output_summary indica residual creada → skipped.
      // Heurística simple: presencia del flag `*_available=false` o
      // `forms_created=0` con `forms_detected>0`.
      if (_hasSkipFlag(phase.output_summary)) return "skipped";
      return "active";
    case "failed":
      return "failed";
    case "running":
      return "pending";
    case "pending":
      return "pending";
    default:
      return "pending";
  }
}

function _hasSkipFlag(summary: unknown): boolean {
  if (!summary || typeof summary !== "object") return false;
  const s = summary as Record<string, unknown>;
  if (s.woocommerce_available === false) return true;
  if (s.gravity_forms_available === false) return true;
  if (typeof s.forms_detected === "number" && s.forms_detected > 0 && s.forms_created === 0) {
    return true;
  }
  return false;
}

interface BadgeProps {
  label: string;
  Icon: typeof ShoppingCart;
  variant: Variant;
  phaseSummary?: Record<string, unknown> | null;
  generatedBy: string;
}

function Badge({ label, Icon, variant, phaseSummary, generatedBy }: BadgeProps) {
  const cls = {
    active:
      "border-wcm-accent/50 bg-wcm-accent/10 text-wcm-accent hover:bg-wcm-accent/15",
    pending:
      "border-wcm-detail/60 bg-wcm-secondary/40 text-muted-foreground hover:text-wcm-text",
    skipped:
      "border-wcm-warning/50 bg-wcm-warning/10 text-wcm-warning hover:bg-wcm-warning/15",
    failed:
      "border-wcm-danger/50 bg-wcm-danger/10 text-wcm-danger hover:bg-wcm-danger/15",
  }[variant];

  const title = _tooltip(label, variant, phaseSummary);

  return (
    <Link
      href={`/residual-tasks?generated_by=${encodeURIComponent(generatedBy)}`}
      className={cn(
        "inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wider transition-colors",
        cls,
      )}
      title={title}
    >
      <Icon className="h-3 w-3" aria-hidden />
      {label}
    </Link>
  );
}

function _tooltip(
  label: string,
  variant: Variant,
  phaseSummary?: Record<string, unknown> | null,
): string {
  const stateLabel = {
    active: "ejecutado correctamente",
    pending: "pendiente",
    skipped: "saltado · revisar checklist",
    failed: "falló · revisar logs",
  }[variant];
  const base = `${label}: ${stateLabel}`;
  if (!phaseSummary) return base;
  if (typeof phaseSummary.products_migrated === "number") {
    return `${base} · ${phaseSummary.products_migrated} productos migrados`;
  }
  if (typeof phaseSummary.forms_created === "number") {
    return `${base} · ${phaseSummary.forms_created}/${phaseSummary.forms_detected ?? 0} forms creados`;
  }
  return base;
}
