"use client";

import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

interface EmailPreviewResponse {
  html: string;
  subject: string | null;
}

interface EmailPreviewIframeProps {
  /** Ruta absoluta del endpoint que devuelve `{html, subject}`.
   *  Ej: `/api/v1/templates/3/preview` o
   *  `/api/v1/outreach/sequences/7/steps/0/preview`. */
  fetchUrl: string;
  /** Etiqueta accesible del iframe. */
  ariaLabel?: string;
  /** Altura fija del iframe en px (default 520). */
  height?: number;
  className?: string;
}

/**
 * Pinta el HTML renderizado de un correo en un iframe sandbox. El
 * iframe usa `srcDoc` (no `src`) para evitar la red — el HTML viene
 * del API ya con CSS inlined por premailer.
 *
 * `sandbox="allow-same-origin"` permite que el HTML se renderice con
 * estilos pero NO ejecuta scripts ni hace navegación — el correo es
 * estático y el cliente solo necesita verlo.
 *
 * Si el fetch falla muestra un mensaje claro; si la URL cambia,
 * re-fetcha (útil al cambiar de step en el editor).
 */
export function EmailPreviewIframe({
  fetchUrl,
  ariaLabel = "Vista previa del correo",
  height = 520,
  className,
}: EmailPreviewIframeProps) {
  const [state, setState] = useState<
    | { kind: "loading" }
    | { kind: "ok"; html: string; subject: string | null }
    | { kind: "error"; message: string }
  >({ kind: "loading" });

  useEffect(() => {
    let alive = true;
    setState({ kind: "loading" });
    async function load() {
      try {
        const data = await api.get<EmailPreviewResponse>(fetchUrl);
        if (alive) setState({ kind: "ok", html: data.html, subject: data.subject });
      } catch (e) {
        if (!alive) return;
        const msg =
          e instanceof ApiError
            ? `${e.status}: ${e.message}`
            : e instanceof Error
              ? e.message
              : "Error desconocido";
        setState({ kind: "error", message: msg });
      }
    }
    void load();
    return () => {
      alive = false;
    };
  }, [fetchUrl]);

  if (state.kind === "loading") {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 text-xs text-muted-foreground",
          className,
        )}
        style={{ height }}
      >
        Cargando vista previa…
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div
        className={cn(
          "rounded-sm border border-wcm-danger/40 bg-wcm-danger/10 p-3 text-xs text-wcm-danger",
          className,
        )}
      >
        <p className="font-semibold">Vista previa no disponible</p>
        <p className="mt-1 text-wcm-text/80">{state.message}</p>
      </div>
    );
  }

  return (
    <div className={cn("space-y-1", className)}>
      {state.subject && (
        <p className="text-[10.5px] uppercase tracking-wider text-muted-foreground">
          Asunto:{" "}
          <span className="text-wcm-text/90 normal-case tracking-normal">
            {state.subject}
          </span>
        </p>
      )}
      <iframe
        title={ariaLabel}
        aria-label={ariaLabel}
        sandbox="allow-same-origin"
        srcDoc={state.html}
        className="w-full rounded-sm border border-wcm-detail/40 bg-white"
        style={{ height }}
      />
    </div>
  );
}
