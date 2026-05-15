"use client";

import { useState } from "react";

import { cn } from "@/lib/utils";

export interface EvidenceItem {
  technology: string;
  category: string;
  confidence: number;
  /** Lista de strings con la evidencia bruta: "html:wp-content/", etc. */
  evidence: string[];
}

interface EvidenceTableProps {
  items: EvidenceItem[];
  /** Si true, arranca expandido. Por defecto colapsado (es info técnica). */
  defaultExpanded?: boolean;
  className?: string;
}

/**
 * Tabla de evidencia del fingerprint, colapsable.
 *
 * Sustituye al dump JSON crudo de la vista anterior. Headers en uppercase
 * pequeño, valores en tabular nums y celdas de evidencia en muted. Por
 * defecto colapsada: ocupa una sola línea con el count y un toggle.
 */
export function EvidenceTable({
  items,
  defaultExpanded = false,
  className,
}: EvidenceTableProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <section className={cn("border-b border-wcm-detail/40 px-7 py-5", className)}>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2.5 text-left"
        aria-expanded={expanded}
      >
        <h3 className="text-[10.5px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
          Evidencia fingerprint
        </h3>
        <span className="text-[10.5px] text-muted-foreground">
          {`${items.length} ${items.length === 1 ? "detección" : "detecciones"}`}
        </span>
        <span className="ml-auto text-[11px] text-muted-foreground hover:text-wcm-text">
          {expanded ? "colapsar ▴" : "expandir ▾"}
        </span>
      </button>

      {expanded && (
        <table className="mt-3 w-full border-collapse text-[11.5px]">
          <thead>
            <tr>
              <Th width="160px">Tecnología</Th>
              <Th width="120px">Categoría</Th>
              <Th width="90px">Confianza</Th>
              <Th>Evidencia</Th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr
                key={`${item.category}-${item.technology}`}
                className="border-b border-wcm-detail/40 last:border-0"
              >
                <td className="py-1.5 pr-2.5 font-medium text-wcm-text">
                  {item.technology}
                </td>
                <td className="py-1.5 pr-2.5 text-[10.5px] uppercase tracking-wide text-muted-foreground">
                  {item.category}
                </td>
                <td className="py-1.5 pr-2.5 tabular-nums text-wcm-text">
                  {item.confidence.toFixed(2)}
                </td>
                <td className="py-1.5 pr-2.5 text-[11px] text-muted-foreground">
                  {item.evidence.join(", ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function Th({
  children,
  width,
}: {
  children: React.ReactNode;
  width?: string;
}) {
  return (
    <th
      style={width ? { width } : undefined}
      className="border-b border-wcm-detail/40 py-1.5 pr-2.5 text-left text-[9.5px] font-semibold uppercase tracking-wider text-muted-foreground"
    >
      {children}
    </th>
  );
}
