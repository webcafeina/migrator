"use client";

import { useState } from "react";

import { cn } from "@/lib/utils";

interface VisualDiffRow {
  id: number;
  page_path: string;
  source_screenshot_url: string | null;
  target_screenshot_url: string | null;
  overlay_url: string | null;
  score: number | null;
  viewport_width: number;
}

interface DiffGalleryProps {
  pages: VisualDiffRow[];
}

type ModalView = {
  page_path: string;
  source: string | null;
  target: string | null;
  overlay: string | null;
} | null;

/**
 * Galería visual diff página-a-página (v0.16.0).
 *
 * Tabla con thumbnail x3 (source / target / overlay) + score badge
 * por fila. Click en cualquier thumbnail abre modal full-size con
 * las 3 imágenes lado a lado para revisión detallada.
 *
 * Score colors:
 * - ≥0.85 verde (lima): igual o muy similar.
 * - 0.70-0.85 ámbar: leves diferencias, revisar.
 * - <0.70 rojo: diferencias significativas, atención.
 */
export function DiffGallery({ pages }: DiffGalleryProps) {
  const [modal, setModal] = useState<ModalView>(null);

  if (pages.length === 0) {
    return (
      <div className="rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-6 text-center text-xs text-muted-foreground">
        No hay comparaciones visuales para este proyecto. Ejecuta el agente{" "}
        <code className="text-wcm-text">visual-diff</code> desde el pipeline.
      </div>
    );
  }

  return (
    <>
      <div className="overflow-hidden rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-wcm-detail/40 bg-wcm-secondary/50 text-[10.5px] uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-2 text-left">Página</th>
              <th className="px-2 py-2 text-center">Score</th>
              <th className="px-2 py-2 text-center">Origen</th>
              <th className="px-2 py-2 text-center">Destino</th>
              <th className="px-2 py-2 text-center">Overlay</th>
            </tr>
          </thead>
          <tbody>
            {pages.map((p) => (
              <tr
                key={p.id}
                className="border-b border-wcm-detail/20 last:border-b-0 hover:bg-wcm-secondary/20"
              >
                <td className="px-4 py-2 font-mono text-[11.5px] text-wcm-text">
                  {p.page_path}
                </td>
                <td className="px-2 py-2 text-center">
                  <ScoreBadge score={p.score} />
                </td>
                <Thumb
                  url={p.source_screenshot_url}
                  onClick={() =>
                    setModal({
                      page_path: p.page_path,
                      source: p.source_screenshot_url,
                      target: p.target_screenshot_url,
                      overlay: p.overlay_url,
                    })
                  }
                  alt={`Origen ${p.page_path}`}
                />
                <Thumb
                  url={p.target_screenshot_url}
                  onClick={() =>
                    setModal({
                      page_path: p.page_path,
                      source: p.source_screenshot_url,
                      target: p.target_screenshot_url,
                      overlay: p.overlay_url,
                    })
                  }
                  alt={`Destino ${p.page_path}`}
                />
                <Thumb
                  url={p.overlay_url}
                  onClick={() =>
                    setModal({
                      page_path: p.page_path,
                      source: p.source_screenshot_url,
                      target: p.target_screenshot_url,
                      overlay: p.overlay_url,
                    })
                  }
                  alt={`Overlay ${p.page_path}`}
                />
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Comparación visual de ${modal.page_path}`}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) setModal(null);
          }}
        >
          <div className="max-h-[95vh] w-full max-w-7xl overflow-y-auto rounded-sm border border-wcm-detail/40 bg-wcm-primary p-4">
            <header className="mb-3 flex items-baseline justify-between">
              <h3 className="font-mono text-sm text-wcm-text">
                {modal.page_path}
              </h3>
              <button
                type="button"
                onClick={() => setModal(null)}
                className="rounded-sm border border-wcm-detail/60 px-2 py-0.5 text-[11px] text-wcm-text/80 hover:border-wcm-detail hover:text-wcm-text"
              >
                Cerrar
              </button>
            </header>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <FullImage url={modal.source} label="Origen" />
              <FullImage url={modal.target} label="Destino" />
              <FullImage url={modal.overlay} label="Overlay (diff en rojo)" />
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score == null) {
    return <span className="text-[11px] text-muted-foreground">—</span>;
  }
  const pct = Math.round(score * 100);
  const cls =
    score >= 0.85
      ? "border-wcm-accent/50 bg-wcm-accent/10 text-wcm-accent"
      : score >= 0.7
        ? "border-wcm-warning/50 bg-wcm-warning/10 text-wcm-warning"
        : "border-wcm-danger/50 bg-wcm-danger/15 text-wcm-danger";
  return (
    <span
      className={cn(
        "inline-flex rounded-sm border px-2 py-0.5 text-[11px] font-semibold tabular-nums",
        cls,
      )}
    >
      {pct}%
    </span>
  );
}

function Thumb({
  url,
  onClick,
  alt,
}: {
  url: string | null;
  onClick: () => void;
  alt: string;
}) {
  if (!url) {
    return (
      <td className="px-2 py-2 text-center">
        <span className="text-[10px] text-muted-foreground">—</span>
      </td>
    );
  }
  // file:// URLs no se pueden renderizar en iframe del dashboard.
  // Muestra un fallback claro.
  const isLocal = url.startsWith("file://");
  return (
    <td className="px-2 py-2 text-center">
      {isLocal ? (
        <span
          className="text-[10px] text-muted-foreground"
          title="R2 no configurado — fichero local"
        >
          (local)
        </span>
      ) : (
        <button
          type="button"
          onClick={onClick}
          className="inline-block overflow-hidden rounded-sm border border-wcm-detail/40 hover:border-wcm-accent"
          aria-label={alt}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={url}
            alt={alt}
            className="h-14 w-24 object-cover object-top"
            loading="lazy"
          />
        </button>
      )}
    </td>
  );
}

function FullImage({ url, label }: { url: string | null; label: string }) {
  return (
    <div className="space-y-1">
      <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
        {label}
      </div>
      {url ? (
        url.startsWith("file://") ? (
          <div className="flex h-64 items-center justify-center rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 text-xs text-muted-foreground">
            Fichero local (configura R2 para visualizar)
          </div>
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={url}
            alt={label}
            className="w-full rounded-sm border border-wcm-detail/40 bg-white"
          />
        )
      ) : (
        <div className="flex h-64 items-center justify-center rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 text-xs text-muted-foreground">
          Sin imagen
        </div>
      )}
    </div>
  );
}
