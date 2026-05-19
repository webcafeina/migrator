"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Settings2 } from "lucide-react";
import { toast } from "sonner";

import { ApiError, api } from "@/lib/api";
import type { ProjectRead } from "@/types/api";

/**
 * ADR-044 + ADR-050 — Configuración avanzada por proyecto.
 *
 * Permite ajustar:
 * - `visual_diff_threshold` (0.0-1.0): umbral pixelmatch bajo el cual
 *   visual-diff genera ResidualTask VISUAL_CONTENT por página.
 * - `max_pages_scrape` (1-500): cap de páginas que el scraper rastrea.
 *
 * Ambos overrides son nullables — null = usa default global (env vars).
 */
export function AdvancedConfigPanel({ project }: { project: ProjectRead }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [open, setOpen] = useState(false);

  const [threshold, setThreshold] = useState<string>(
    project.visual_diff_threshold !== null &&
      project.visual_diff_threshold !== undefined
      ? String(project.visual_diff_threshold)
      : "",
  );
  const [maxPages, setMaxPages] = useState<string>(
    project.max_pages_scrape !== null && project.max_pages_scrape !== undefined
      ? String(project.max_pages_scrape)
      : "",
  );

  function save() {
    const payload: Record<string, unknown> = {};
    if (threshold.trim() === "") {
      payload.visual_diff_threshold = null;
    } else {
      const v = parseFloat(threshold);
      if (Number.isNaN(v) || v < 0 || v > 1) {
        toast.error("visual_diff_threshold debe estar entre 0.0 y 1.0");
        return;
      }
      payload.visual_diff_threshold = v;
    }
    if (maxPages.trim() === "") {
      payload.max_pages_scrape = null;
    } else {
      const v = parseInt(maxPages, 10);
      if (Number.isNaN(v) || v < 1 || v > 500) {
        toast.error("max_pages_scrape debe estar entre 1 y 500");
        return;
      }
      payload.max_pages_scrape = v;
    }
    startTransition(async () => {
      try {
        await api.patch(`/api/v1/projects/${project.id}`, payload);
        toast.success("Configuración avanzada actualizada");
        router.refresh();
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Error inesperado");
      }
    });
  }

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground hover:text-wcm-text"
      >
        <Settings2 className="h-3 w-3" />
        Configuración avanzada {open ? "▾" : "▸"}
      </button>
      {open && (
        <div className="space-y-3 rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-4 text-xs">
          <div className="space-y-1">
            <label
              htmlFor={`vt-${project.id}`}
              className="block text-[10px] uppercase tracking-wider text-muted-foreground"
            >
              visual_diff_threshold (0.0-1.0)
            </label>
            <input
              id={`vt-${project.id}`}
              type="number"
              step="0.01"
              min="0"
              max="1"
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
              placeholder="usar global (env)"
              className="w-32 rounded-sm border border-wcm-detail bg-wcm-primary px-2 py-1 font-mono text-xs text-wcm-text"
            />
            <p className="text-[10px] text-muted-foreground">
              Páginas con score &lt; este umbral generan ResidualTask. Vacío =
              usa <code>VISUAL_DIFF_RESIDUAL_THRESHOLD</code> (0.70 default).
            </p>
          </div>
          <div className="space-y-1">
            <label
              htmlFor={`mp-${project.id}`}
              className="block text-[10px] uppercase tracking-wider text-muted-foreground"
            >
              max_pages_scrape (1-500)
            </label>
            <input
              id={`mp-${project.id}`}
              type="number"
              step="1"
              min="1"
              max="500"
              value={maxPages}
              onChange={(e) => setMaxPages(e.target.value)}
              placeholder="usar global (env)"
              className="w-32 rounded-sm border border-wcm-detail bg-wcm-primary px-2 py-1 font-mono text-xs text-wcm-text"
            />
            <p className="text-[10px] text-muted-foreground">
              Cap de páginas a scrapear. Vacío = usa{" "}
              <code>SCRAPE_MAX_PAGES_DEFAULT</code> (50 default).
            </p>
          </div>
          <button
            type="button"
            onClick={save}
            disabled={pending}
            className="rounded-sm bg-wcm-accent px-3 py-1 text-[11px] font-semibold text-wcm-primary hover:brightness-110 disabled:opacity-40"
          >
            {pending ? "Guardando…" : "Guardar"}
          </button>
        </div>
      )}
    </div>
  );
}
