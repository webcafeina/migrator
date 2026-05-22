"use client";

/**
 * `<RefinementPanel />` — panel lateral con propuestas de mejora del Brief
 * generadas por gpt-5.5 (Sprint v0.27.0 B6).
 *
 * Flujo:
 * 1. Operador hace click en "🪄 Sugerir mejoras" (PreviewPanel header).
 * 2. POST /brief/suggest-refinements encola task Celery.
 * 3. Panel hace fetch a GET /brief/refinements y muestra propuestas.
 * 4. Por cada propuesta: DiffViewer + 2 botones ("Aplicar al Brief" /
 *    "Aplicar + regenerar"). Marca como aplicada cuando applied_at != null.
 */

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  Check,
  Loader2,
  RotateCw,
  Sparkles,
  X,
} from "lucide-react";

import { DiffViewer } from "@/components/diff-viewer";
import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface RefinementProposal {
  id: string;
  category: "copy" | "cta" | "design_method" | "reorder";
  page_slug: string;
  section_index: number;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  rationale: string;
  impact_estimate: "low" | "medium" | "high";
  applied_at: string | null;
}

interface RefinementsResponse {
  project_id: number;
  generated_at: string | null;
  model: string | null;
  cost_usd: number;
  tokens_in: number;
  tokens_out: number;
  proposals: RefinementProposal[];
}

interface RefinementPanelProps {
  projectId: number;
  onClose: () => void;
}

export function RefinementPanel({ projectId, onClose }: RefinementPanelProps) {
  const router = useRouter();
  const [data, setData] = useState<RefinementsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [, startTransition] = useTransition();
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<RefinementsResponse>(
        `/api/v1/projects/${projectId}/brief/refinements`,
      );
      setData(res);
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Error cargando propuestas",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  function handleApply(
    proposal: RefinementProposal,
    regenerate: boolean,
  ) {
    setApplyingId(proposal.id);
    setError(null);
    startTransition(async () => {
      try {
        await api.post(
          `/api/v1/projects/${projectId}/brief/apply-refinement`,
          { proposal_id: proposal.id, regenerate },
        );
        await load();
        router.refresh();
      } catch (e) {
        setError(
          e instanceof ApiError ? e.message : "Error aplicando propuesta",
        );
      } finally {
        setApplyingId(null);
      }
    });
  }

  function handleDismiss(proposalId: string) {
    setDismissed((prev) => new Set([...prev, proposalId]));
  }

  const proposals = (data?.proposals ?? []).filter(
    (p) => !dismissed.has(p.id),
  );
  const grouped = groupByPageAndCategory(proposals);
  const appliedCount = proposals.filter((p) => p.applied_at).length;

  return (
    <aside className="fixed inset-y-0 right-0 z-40 flex w-full max-w-md flex-col border-l border-wcm-detail/60 bg-wcm-secondary shadow-2xl">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-wcm-detail/40 p-3">
        <div>
          <h3 className="flex items-center gap-1.5 text-xs font-semibold text-wcm-accent">
            <Sparkles className="h-3.5 w-3.5" aria-hidden />
            Sugerencias de mejora (AI)
          </h3>
          {data && data.generated_at && (
            <p className="mt-0.5 text-[10px] text-muted-foreground">
              {data.model} · ${data.cost_usd.toFixed(4)} ·{" "}
              {new Date(data.generated_at).toLocaleString("es-ES", {
                dateStyle: "short",
                timeStyle: "short",
              })}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-sm border border-wcm-detail/60 p-1 hover:border-wcm-accent"
          title="Cerrar panel"
        >
          <X className="h-3 w-3" aria-hidden />
        </button>
      </header>

      {error && (
        <div className="border-b border-wcm-danger/40 bg-wcm-danger/10 p-2 text-[11px] text-wcm-danger">
          {error}
        </div>
      )}

      {/* Cuerpo */}
      <div className="flex-1 overflow-y-auto p-3 text-[11px]">
        {loading ? (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
            Cargando propuestas...
          </div>
        ) : proposals.length === 0 ? (
          <p className="italic text-muted-foreground">
            Aún no hay propuestas. Haz click en{" "}
            <strong>"Sugerir mejoras (AI)"</strong> en el panel principal
            para generar la primera batch.
          </p>
        ) : (
          <ul className="space-y-3">
            {Object.entries(grouped).map(([pageSlug, byCategory]) => (
              <li key={pageSlug}>
                <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  página /{pageSlug}
                </h4>
                <ul className="space-y-2">
                  {Object.entries(byCategory).flatMap(([cat, props]) =>
                    props.map((p) => (
                      <li
                        key={p.id}
                        className={cn(
                          "rounded-sm border p-2",
                          p.applied_at
                            ? "border-wcm-accent/40 bg-wcm-accent/5"
                            : "border-wcm-detail/40 bg-wcm-primary/40",
                        )}
                      >
                        <div className="mb-1 flex flex-wrap items-center gap-1.5">
                          <CategoryBadge cat={cat as RefinementProposal["category"]} />
                          <ImpactBadge impact={p.impact_estimate} />
                          <span className="text-[10px] text-muted-foreground">
                            sección #{p.section_index}
                          </span>
                          {p.applied_at && (
                            <span className="inline-flex items-center gap-0.5 text-[10px] text-wcm-accent">
                              <Check className="h-2.5 w-2.5" aria-hidden />
                              aplicada
                            </span>
                          )}
                        </div>
                        <DiffViewer
                          before={p.before}
                          after={p.after}
                          className="mb-1"
                        />
                        <p className="mb-1.5 text-[10.5px] italic text-muted-foreground">
                          {p.rationale}
                        </p>
                        {!p.applied_at && (
                          <div className="flex flex-wrap gap-1">
                            <button
                              type="button"
                              onClick={() => handleApply(p, false)}
                              disabled={applyingId === p.id}
                              className="inline-flex items-center gap-1 rounded-sm border border-wcm-detail/60 bg-wcm-primary px-1.5 py-0.5 text-[10px] hover:border-wcm-accent disabled:cursor-not-allowed disabled:opacity-50"
                              title="Solo edita el Brief. No regenera el draft WP."
                            >
                              {applyingId === p.id ? (
                                <Loader2 className="h-2.5 w-2.5 animate-spin" aria-hidden />
                              ) : (
                                <Check className="h-2.5 w-2.5" aria-hidden />
                              )}
                              aplicar al Brief
                            </button>
                            <button
                              type="button"
                              onClick={() => handleApply(p, true)}
                              disabled={applyingId === p.id}
                              className="inline-flex items-center gap-1 rounded-sm bg-wcm-accent px-1.5 py-0.5 text-[10px] font-semibold text-wcm-primary hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
                              title="Edita Brief + dispara regenerate de la página afectada."
                            >
                              {applyingId === p.id ? (
                                <Loader2 className="h-2.5 w-2.5 animate-spin" aria-hidden />
                              ) : (
                                <RotateCw className="h-2.5 w-2.5" aria-hidden />
                              )}
                              aplicar + regenerar
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDismiss(p.id)}
                              disabled={applyingId === p.id}
                              className="inline-flex items-center gap-1 rounded-sm border border-wcm-detail/40 px-1.5 py-0.5 text-[10px] text-muted-foreground hover:text-wcm-text disabled:opacity-50"
                              title="Ocultar de la lista (no persiste)"
                            >
                              <X className="h-2.5 w-2.5" aria-hidden />
                              descartar
                            </button>
                          </div>
                        )}
                      </li>
                    )),
                  )}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Footer */}
      {data && proposals.length > 0 && (
        <footer className="border-t border-wcm-detail/40 p-2 text-[10px] text-muted-foreground">
          {appliedCount} aplicadas / {proposals.length} total · coste real ${data.cost_usd.toFixed(4)}
        </footer>
      )}
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Helpers UI
// ---------------------------------------------------------------------------

function groupByPageAndCategory(
  proposals: RefinementProposal[],
): Record<string, Record<string, RefinementProposal[]>> {
  const out: Record<string, Record<string, RefinementProposal[]>> = {};
  for (const p of proposals) {
    const page = (out[p.page_slug] ??= {});
    const cat = (page[p.category] ??= []);
    cat.push(p);
  }
  return out;
}

function CategoryBadge({ cat }: { cat: RefinementProposal["category"] }) {
  const colors: Record<RefinementProposal["category"], string> = {
    copy: "border-blue-500/40 bg-blue-500/10 text-blue-300",
    cta: "border-purple-500/40 bg-purple-500/10 text-purple-300",
    design_method: "border-amber-500/40 bg-amber-500/10 text-amber-300",
    reorder: "border-pink-500/40 bg-pink-500/10 text-pink-300",
  };
  return (
    <span
      className={cn(
        "rounded-sm border px-1.5 py-0.5 text-[9.5px] uppercase tracking-wider",
        colors[cat],
      )}
    >
      {cat}
    </span>
  );
}

function ImpactBadge({
  impact,
}: {
  impact: RefinementProposal["impact_estimate"];
}) {
  const colors: Record<RefinementProposal["impact_estimate"], string> = {
    low: "border-wcm-detail/40 text-muted-foreground",
    medium: "border-wcm-warning/40 bg-wcm-warning/10 text-wcm-warning",
    high: "border-wcm-accent/40 bg-wcm-accent/10 text-wcm-accent",
  };
  return (
    <span
      className={cn(
        "rounded-sm border px-1 py-0.5 text-[9.5px] uppercase tracking-wider",
        colors[impact],
      )}
    >
      impact {impact}
    </span>
  );
}
