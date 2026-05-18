"use client";

import { useMemo, useState } from "react";

import { cn } from "@/lib/utils";

import { type BulkParseResult, parseBulkUrls } from "./parse-bulk-urls";

interface BulkPreviewProps {
  raw: string;
  /** Llamado cada vez que cambia el set de URLs válidas. El padre lo
   * usa para habilitar/deshabilitar el botón submit y para el payload. */
  onParsed: (result: BulkParseResult) => void;
}

/**
 * Resumen visual del contenido del textarea: cuántas URLs válidas vs
 * inválidas, con lista expandible de las inválidas (línea + texto)
 * para que el operador pueda corregir antes de enviar.
 *
 * Estado vacío: copy explicativo de las reglas (1 por línea, # ignora).
 */
export function BulkPreview({ raw, onParsed }: BulkPreviewProps) {
  const [showInvalid, setShowInvalid] = useState(false);

  const result = useMemo(() => {
    const r = parseBulkUrls(raw);
    onParsed(r);
    return r;
    // onParsed se considera estable; si no lo es, padre lo envuelve.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [raw]);

  if (raw.trim() === "") {
    return (
      <p className="text-[11px] text-muted-foreground">
        Pega 1 URL por línea. Líneas con <code>#</code> se ignoran.
      </p>
    );
  }

  const total = result.valid.length + result.invalid.length;
  const overLimit = result.valid.length > 200;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-[10.5px]">
        <Badge tone="ok">
          {result.valid.length} URL{result.valid.length === 1 ? "" : "s"} válida{result.valid.length === 1 ? "" : "s"}
        </Badge>
        {result.invalid.length > 0 && (
          <button
            type="button"
            onClick={() => setShowInvalid((v) => !v)}
            className="rounded-sm border border-wcm-warning/40 bg-wcm-warning/10 px-1.5 py-0.5 uppercase tracking-wider text-wcm-warning hover:bg-wcm-warning/20"
          >
            {result.invalid.length} a ignorar {showInvalid ? "▴" : "▾"}
          </button>
        )}
        <span className="text-muted-foreground">
          · de {total} línea{total === 1 ? "" : "s"} no vacías
        </span>
        {overLimit && (
          <Badge tone="error">
            Máximo 200 por lote — divide en partes
          </Badge>
        )}
      </div>

      {showInvalid && result.invalid.length > 0 && (
        <ul className="space-y-1 rounded-sm border border-wcm-warning/30 bg-wcm-warning/5 p-2 text-[11px] text-wcm-text/80">
          {result.invalid.slice(0, 20).map((item) => (
            <li key={item.line} className="flex gap-2 font-mono">
              <span className="shrink-0 text-muted-foreground">
                L{item.line}:
              </span>
              <span className="break-all">{item.raw}</span>
            </li>
          ))}
          {result.invalid.length > 20 && (
            <li className="text-muted-foreground">
              … y {result.invalid.length - 20} más
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

function Badge({
  children,
  tone,
}: {
  children: React.ReactNode;
  tone: "ok" | "error";
}) {
  return (
    <span
      className={cn(
        "inline-flex rounded-sm border px-1.5 py-0.5 uppercase tracking-wider",
        tone === "ok"
          ? "border-wcm-accent/50 bg-wcm-accent/10 text-wcm-accent"
          : "border-wcm-danger/50 bg-wcm-danger/15 text-wcm-danger font-semibold",
      )}
    >
      {children}
    </span>
  );
}
