import Link from "next/link";

import { cn, formatRelativeTime } from "@/lib/utils";
import type { ErrorLogRead } from "@/types/api";

interface ErrorsTableProps {
  errors: ErrorLogRead[];
  className?: string;
}

/**
 * Tabla de entradas de `error_log` para el rediseño de /errors.
 *
 * Columnas (priorizadas por utilidad operativa al diagnosticar):
 * 1. CUÁNDO — tiempo relativo (los recientes pesan más).
 * 2. SEVERIDAD — badge color por nivel.
 * 3. COMPONENTE — qué subagente / módulo falló.
 * 4. MENSAJE — con line-clamp; el operador hace hover/click para
 *    expandir si necesita el detalle completo.
 * 5. PROYECTO — link al proyecto si está asociado.
 *
 * Responsive: oculta componente + proyecto en estrecho, deja cuándo +
 * severidad + mensaje (las críticas para diagnosticar).
 *
 * Presentacional puro: devuelve `null` con lista vacía — empty state
 * al padre.
 */
export function ErrorsTable({ errors, className }: ErrorsTableProps) {
  if (errors.length === 0) return null;

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
            <Th width="100px">Cuándo</Th>
            <Th width="100px">Severidad</Th>
            <Th width="180px" hideUntil="md">
              Componente
            </Th>
            <Th>Mensaje</Th>
            <Th width="80px" hideUntil="md">
              Proyecto
            </Th>
          </tr>
        </thead>
        <tbody>
          {errors.map((e) => (
            <Row key={e.id} entry={e} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Row({ entry }: { entry: ErrorLogRead }) {
  return (
    <tr className="border-t border-wcm-detail/40 transition-colors hover:bg-wcm-secondary/30">
      <td className="px-4 py-2.5 tabular-nums text-wcm-text/70">
        {formatRelativeTime(entry.at)}
      </td>
      <td className="px-4 py-2.5">
        <SeverityBadge severity={entry.severity} />
      </td>
      <td className="hidden px-4 py-2.5 text-wcm-text/80 md:table-cell">
        <code className="text-wcm-text">{entry.component}</code>
      </td>
      <td className="px-4 py-2.5">
        <div
          className="line-clamp-2 text-wcm-text"
          title={entry.message}
        >
          {entry.message}
        </div>
      </td>
      <td className="hidden px-4 py-2.5 md:table-cell">
        {entry.project_id != null ? (
          <Link
            href={`/projects/${entry.project_id}`}
            className="tabular-nums text-wcm-text/70 hover:text-wcm-accent"
          >
            {`#${entry.project_id}`}
          </Link>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </td>
    </tr>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    critical: {
      label: "crítico",
      cls: "border-wcm-danger/50 bg-wcm-danger/15 text-wcm-danger font-semibold",
    },
    error: {
      label: "error",
      cls: "border-wcm-danger/40 text-wcm-danger",
    },
    warning: {
      label: "warning",
      cls: "border-wcm-warning/40 text-wcm-warning",
    },
    info: {
      label: "info",
      cls: "border-wcm-detail/60 text-wcm-text/70",
    },
    debug: {
      label: "debug",
      cls: "border-wcm-detail/60 text-muted-foreground",
    },
  };
  const spec = map[severity] ?? {
    label: severity,
    cls: "border-wcm-detail/60 text-wcm-text/70",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm border px-2 py-0.5 text-[10.5px] uppercase tracking-wider",
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
