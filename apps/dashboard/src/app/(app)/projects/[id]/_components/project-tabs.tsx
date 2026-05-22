"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ClipboardCheck,
  Eye,
  GaugeCircle,
  GitCompare,
  LayoutDashboard,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

interface ProjectTabsProps {
  projectId: number;
  /** Conteos opcionales para mostrar al lado del label de cada tab. */
  counts?: {
    residualOpen?: number;
  };
  className?: string;
}

interface TabSpec {
  label: string;
  icon: LucideIcon;
  /** Sufijo del path tras `/projects/{id}`. "" = overview. */
  suffix: string;
}

const TABS: TabSpec[] = [
  { label: "Overview", icon: LayoutDashboard, suffix: "" },
  { label: "Preview", icon: Eye, suffix: "/preview" },
  { label: "Checklist", icon: ClipboardCheck, suffix: "/checklist" },
  { label: "Visual diff", icon: GitCompare, suffix: "/diff" },
  { label: "QA", icon: GaugeCircle, suffix: "/qa" },
];

/**
 * Tabs entre las 3 sub-páginas del proyecto. Resalta la activa según
 * pathname. Sin estado interno; la navegación es real (Next router).
 *
 * El tab "Checklist" muestra count de residuales abiertas si se
 * proporciona — el operador ve si hay tareas pendientes sin entrar.
 */
export function ProjectTabs({
  projectId,
  counts,
  className,
}: ProjectTabsProps) {
  const pathname = usePathname() ?? "";
  const base = `/projects/${projectId}`;

  return (
    <nav
      className={cn(
        "flex gap-1 border-b border-wcm-detail/40",
        className,
      )}
      aria-label="Secciones del proyecto"
    >
      {TABS.map((tab) => {
        const href = `${base}${tab.suffix}`;
        // Active matcher: el overview ("") solo si el pathname termina
        // exactamente en /projects/{id} sin sufijo; el resto exact-match.
        const isActive =
          tab.suffix === ""
            ? pathname === base
            : pathname === href;
        const Icon = tab.icon;
        const badge =
          tab.suffix === "/checklist" &&
          counts?.residualOpen != null &&
          counts.residualOpen > 0
            ? counts.residualOpen
            : null;
        return (
          <Link
            key={tab.suffix}
            href={href}
            aria-current={isActive ? "page" : undefined}
            className={cn(
              "relative inline-flex items-center gap-2 border-b-2 px-4 py-2 text-xs transition-colors",
              isActive
                ? "border-wcm-accent text-wcm-text"
                : "border-transparent text-muted-foreground hover:text-wcm-text",
            )}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden />
            {tab.label}
            {badge != null && (
              <span
                className={cn(
                  "rounded-sm px-1.5 py-px text-[10px] tabular-nums",
                  isActive
                    ? "bg-wcm-accent text-wcm-primary font-semibold"
                    : "bg-wcm-warning/15 text-wcm-warning",
                )}
              >
                {badge}
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );
}
