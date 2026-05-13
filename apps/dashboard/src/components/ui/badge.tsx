import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-semibold uppercase tracking-wider",
  {
    variants: {
      variant: {
        default: "border-wcm-accent/30 bg-wcm-accent/10 text-wcm-accent",
        neutral: "border-wcm-detail bg-wcm-primary/50 text-wcm-text",
        success: "border-wcm-accent/40 bg-wcm-accent/15 text-wcm-accent",
        warning: "border-wcm-warning/40 bg-wcm-warning/15 text-wcm-warning",
        danger: "border-wcm-danger/40 bg-wcm-danger/15 text-wcm-danger",
        muted: "border-wcm-detail/40 bg-transparent text-wcm-detail",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

/**
 * Mapping de status del dominio → variant del Badge.
 * Centralizado aquí para coherencia visual en todas las tablas.
 */
export function statusVariant(status: string): BadgeProps["variant"] {
  const s = status.toLowerCase();
  if (["completed", "success", "ready", "done"].includes(s)) return "success";
  if (["queued", "pending", "draft_pending_review"].includes(s)) return "neutral";
  if (["running", "in_progress", "fingerprinted", "enriched"].includes(s)) return "default";
  if (["blocked_human_input", "blocked", "qa_failed", "paused"].includes(s)) return "warning";
  if (["failed", "cancelled", "opted_out", "discarded"].includes(s)) return "danger";
  return "muted";
}
