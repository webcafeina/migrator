import { cn } from "@/lib/utils";

export interface FingerprintItem {
  /** Nombre legible de la tecnología detectada. Ej. "WordPress". */
  technology: string;
  /** Categoría: cms, builder, analytics, ecommerce, etc. */
  category: string;
  /** Confianza 0..1 reportada por el fingerprinter. */
  confidence: number;
}

interface FingerprintListProps {
  items: FingerprintItem[];
  className?: string;
}

/**
 * Render compacto de las detecciones del fingerprinter para el detalle
 * del lead. Cada item: categoría a la izquierda (muted), tecnología en
 * el centro, barra de confianza inline y valor numérico a la derecha.
 *
 * Lista vacía → mensaje muted breve (la API debería garantizar al menos
 * 1 item para un lead enriquecido, pero defendemos).
 */
export function FingerprintList({ items, className }: FingerprintListProps) {
  if (items.length === 0) {
    return (
      <p className={cn("text-xs text-muted-foreground", className)}>
        Sin detecciones registradas.
      </p>
    );
  }

  return (
    <ul className={cn("flex flex-col gap-2.5", className)}>
      {items.map((item) => {
        const pct = Math.max(0, Math.min(1, item.confidence)) * 100;
        return (
          <li
            key={`${item.category}-${item.technology}`}
            className="flex items-center gap-3 text-xs"
          >
            <span className="w-[92px] shrink-0 text-muted-foreground">
              {item.category}
            </span>
            <span className="font-medium text-wcm-text">{item.technology}</span>
            <span
              className="ml-auto h-1 max-w-[140px] flex-1 rounded-[1px] bg-wcm-secondary"
              aria-label={`Confianza ${item.confidence.toFixed(2)}`}
            >
              <span
                className="block h-full rounded-[1px] bg-wcm-accent"
                style={{ width: `${pct}%` }}
              />
            </span>
            <span className="w-10 shrink-0 text-right tabular-nums text-wcm-text/70">
              {item.confidence.toFixed(2)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
