"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  Briefcase,
  CheckSquare,
  LayoutGrid,
  Settings,
  Target,
  Users,
} from "lucide-react";

import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const NAV: NavItem[] = [
  { href: "/", label: "Panel", icon: LayoutGrid },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/projects", label: "Proyectos", icon: Briefcase },
  { href: "/campaigns", label: "Campañas", icon: Target },
  { href: "/residual-tasks", label: "Tareas pendientes", icon: CheckSquare },
  { href: "/errors", label: "Errores", icon: AlertTriangle },
  { href: "/settings", label: "Ajustes", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden md:flex w-[220px] shrink-0 flex-col border-r border-wcm-detail bg-wcm-primary">
      {/* Wordmark — logo SVG pendiente; placeholder texto en lima */}
      <div className="flex items-center gap-2 border-b border-wcm-detail px-4 py-4">
        <Activity className="h-5 w-5 text-wcm-accent" strokeWidth={2.5} />
        <span className="text-wcm-accent font-bold tracking-tighter text-sm">
          WEBCAFEÍNA
        </span>
      </div>

      <nav className="flex-1 space-y-0.5 p-2">
        {NAV.map((item) => {
          const Icon = item.icon;
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-sm px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-wcm-secondary text-wcm-accent border-l-2 border-wcm-accent"
                  : "text-wcm-text hover:bg-wcm-secondary hover:text-wcm-accent border-l-2 border-transparent",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-wcm-detail p-3 text-xs text-wcm-detail">
        <div>migrator v0.3.0</div>
        <div className="opacity-60">interno · {new Date().getFullYear()}</div>
      </div>
    </aside>
  );
}
