"use client";

import { useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { cn } from "@/lib/utils";

export interface FilterChip {
  /** Identificador interno único (ej. "sector:marketing"). */
  id: string;
  /** Texto visible del chip. */
  label: string;
  /** Conteo opcional ("12"). */
  count?: number;
  /** Param de URL ("sector"). */
  param: string;
  /** Valor que toma cuando se activa ("marketing"). */
  value: string;
}

interface FilterChipsProps {
  chips: FilterChip[];
  className?: string;
}

/**
 * Chips toggle de filtro que se sincronizan con la query string. Click
 * en un chip activa/desactiva el filtro correspondiente y dispara
 * `router.replace(...)` con el query actualizado.
 *
 * Soporta múltiples filtros del mismo `param` (toggle exclusivo por
 * param: solo un valor activo por param a la vez — patrón Linear).
 * Si tu caso necesita multi-valor, ampliamos a CSV.
 */
export function FilterChips({ chips, className }: FilterChipsProps) {
  const router = useRouter();
  const params = useSearchParams();

  const toggle = useCallback(
    (chip: FilterChip) => {
      const next = new URLSearchParams(params.toString());
      const current = next.get(chip.param);
      if (current === chip.value) {
        next.delete(chip.param);
      } else {
        next.set(chip.param, chip.value);
      }
      // Mantenemos `selected` (lead activo) si existía.
      const qs = next.toString();
      router.replace(qs ? `?${qs}` : "?", { scroll: false });
    },
    [params, router],
  );

  return (
    <div className={cn("flex flex-wrap gap-1.5 pt-0.5", className)}>
      {chips.map((chip) => {
        const active = params.get(chip.param) === chip.value;
        return (
          <button
            key={chip.id}
            type="button"
            onClick={() => toggle(chip)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-2 py-[3px] text-[10.5px] transition-colors",
              active
                ? "border-wcm-accent bg-wcm-accent/[0.08] text-wcm-accent"
                : "border-wcm-detail/60 text-wcm-text/70 hover:border-muted-foreground hover:text-wcm-text",
            )}
            aria-pressed={active}
          >
            {chip.label}
            {chip.count !== undefined && (
              <span
                className={cn(
                  "tabular-nums",
                  active ? "text-wcm-accent/70" : "text-muted-foreground",
                )}
              >
                {chip.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
