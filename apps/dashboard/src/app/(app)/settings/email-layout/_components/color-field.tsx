"use client";

import { useId } from "react";

import { cn } from "@/lib/utils";

interface ColorFieldProps {
  label: string;
  /** HEX 6 chars, formato `#RRGGBB`. */
  value: string;
  onChange: (hex: string) => void;
  /** Descripción corta debajo del label (opcional). */
  hint?: string;
  disabled?: boolean;
  className?: string;
}

const HEX_RE = /^#[0-9A-Fa-f]{6}$/;

/**
 * Campo reutilizable para el tema visual del layout (v0.15.0).
 *
 * Combina un `<input type="color">` nativo (color picker del SO) con
 * un text input HEX al lado sincronizado. Validación cliente del HEX
 * antes de propagar al padre — si el usuario escribe algo inválido,
 * el text queda en rojo pero no dispara onChange (evita 422 ruidosos).
 */
export function ColorField({
  label,
  value,
  onChange,
  hint,
  disabled = false,
  className,
}: ColorFieldProps) {
  const id = useId();
  const isValidHex = HEX_RE.test(value);

  function handleTextChange(raw: string) {
    // Permitir escritura libre sin validar, pero solo propagar si
    // queda HEX válido (los componentes consumidores se quedan en
    // último valor válido conocido).
    const next = raw.startsWith("#") ? raw : `#${raw}`;
    if (HEX_RE.test(next)) {
      onChange(next.toUpperCase());
    }
  }

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <label
        htmlFor={id}
        className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground"
      >
        {label}
      </label>
      <div className="flex items-center gap-2">
        <input
          id={id}
          type="color"
          value={isValidHex ? value : "#000000"}
          onChange={(e) => onChange(e.target.value.toUpperCase())}
          disabled={disabled}
          className="h-7 w-10 cursor-pointer rounded-sm border border-wcm-detail/70 bg-wcm-primary disabled:opacity-50"
          aria-label={`Selector de color para ${label}`}
        />
        <input
          type="text"
          value={value}
          onChange={(e) => handleTextChange(e.target.value)}
          disabled={disabled}
          maxLength={7}
          spellCheck={false}
          className={cn(
            "h-7 w-24 rounded-sm border bg-wcm-primary px-2 font-mono text-[11px] text-wcm-text focus:outline-none disabled:opacity-50",
            isValidHex
              ? "border-wcm-detail/70 focus:border-wcm-accent"
              : "border-wcm-danger focus:border-wcm-danger",
          )}
          aria-label={`HEX para ${label}`}
        />
      </div>
      {hint && <p className="text-[10px] text-muted-foreground">{hint}</p>}
    </div>
  );
}
