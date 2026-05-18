"use client";

import { useCallback, useEffect, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { cn } from "@/lib/utils";
import type { LeadRead } from "@/types/api";

import type { FilterChip } from "@/components/filter-chips";
import { LeadDetailPane } from "./lead-detail-pane";
import { LeadList } from "./lead-list";
import { TopbarStats, type TopbarStatsData } from "./topbar-stats";

interface LeadsWorkspaceProps {
  leads: LeadRead[];
  stats: TopbarStatsData;
  /** Médiana del score por sector (calculada en server). */
  sectorMedians: Record<string, number>;
}

/**
 * Orquestador del rediseño master-detail. Gestiona la selección (sincro
 * URL ?selected=N), construye los chips de filtro desde el conjunto real
 * de leads, y compone el layout 3 columnas: sidebar (fuera) · lista 420px ·
 * detalle.
 *
 * Trabaja en client porque la selección debe ser instantánea (sin
 * round-trip al server). El fetch inicial lo hace el page.tsx (Server)
 * y pasa el array completo aquí — para <30 leads es trivialmente
 * eficiente; a escala mayor se paginará.
 */
export function LeadsWorkspace({
  leads,
  stats,
  sectorMedians,
}: LeadsWorkspaceProps) {
  const router = useRouter();
  const params = useSearchParams();

  const selectedId = parseIdParam(params.get("selected"));
  const selectedLead = useMemo(
    () => (selectedId == null ? null : leads.find((l) => l.id === selectedId) ?? null),
    [leads, selectedId],
  );

  const select = useCallback(
    (id: number) => {
      const next = new URLSearchParams(params.toString());
      next.set("selected", String(id));
      router.replace(`?${next.toString()}`, { scroll: false });
    },
    [params, router],
  );

  const filterChips = useMemo<FilterChip[]>(
    () => buildFilterChips(leads),
    [leads],
  );

  // Lista ordenada idéntica a la que renderiza LeadList — usada por los
  // atajos de teclado para resolver "siguiente" / "anterior".
  const orderedIds = useMemo(() => {
    const uncontactedStatuses = new Set([
      "discovered",
      "fingerprinted",
      "enriched",
    ]);
    const sortByScoreDesc = (a: LeadRead, b: LeadRead) => b.score - a.score;
    return [
      ...leads
        .filter((l) => uncontactedStatuses.has(l.status))
        .sort(sortByScoreDesc),
      ...leads
        .filter((l) => !uncontactedStatuses.has(l.status))
        .sort(sortByScoreDesc),
    ].map((l) => l.id);
  }, [leads]);

  const moveSelection = useCallback(
    (delta: 1 | -1) => {
      if (orderedIds.length === 0) return;
      const currentIdx = selectedId == null ? -1 : orderedIds.indexOf(selectedId);
      const nextIdx =
        currentIdx === -1
          ? delta === 1
            ? 0
            : orderedIds.length - 1
          : Math.max(0, Math.min(orderedIds.length - 1, currentIdx + delta));
      const nextId = orderedIds[nextIdx];
      if (nextId != null && nextId !== selectedId) select(nextId);
    },
    [orderedIds, selectedId, select],
  );

  // Atajos de teclado. Se enganchan al document para no requerir focus
  // en ningún elemento. Se ignoran cuando el usuario está editando un
  // input/textarea/select para no interferir con la búsqueda futura.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement | null)?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select") return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          moveSelection(1);
          break;
        case "ArrowUp":
          e.preventDefault();
          moveSelection(-1);
          break;
        case "Enter":
          if (selectedId != null) {
            e.preventDefault();
            router.push(`/leads/${selectedId}`);
          }
          break;
        case "Escape":
          if (selectedId != null) {
            e.preventDefault();
            const next = new URLSearchParams(params.toString());
            next.delete("selected");
            router.replace(next.toString() ? `?${next.toString()}` : "?", {
              scroll: false,
            });
          }
          break;
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [moveSelection, selectedId, router, params]);

  // Percentil del lead seleccionado dentro del set actual.
  const percentile = useMemo(() => {
    if (!selectedLead) return null;
    const sorted = leads
      .map((l) => l.score)
      .filter((s) => s > 0)
      .sort((a, b) => a - b);
    if (sorted.length === 0) return null;
    const idx = sorted.findIndex((s) => s >= selectedLead.score);
    return Math.round((idx / sorted.length) * 100);
  }, [leads, selectedLead]);

  const sectorMedian =
    selectedLead?.sector != null
      ? sectorMedians[selectedLead.sector] ?? null
      : null;

  const closeDetail = useCallback(() => {
    const next = new URLSearchParams(params.toString());
    next.delete("selected");
    router.replace(next.toString() ? `?${next.toString()}` : "?", {
      scroll: false,
    });
  }, [params, router]);

  return (
    // -m-6 anula el padding del `<main>` del layout `(app)/layout.tsx` para
    // que el workspace ocupe edge-to-edge. El resto de páginas mantienen
    // el padding global; este rediseño es la excepción.
    <div className="-m-6 flex h-[calc(100vh-3.5rem)] flex-col">
      <div className="flex h-[44px] shrink-0 items-center border-b border-wcm-detail/40 bg-wcm-primary px-4">
        <TopbarStats stats={stats} />
      </div>
      <div
        className={cn(
          // Layout: dos columnas a partir de xl (≥1280px); una sola
          // columna por debajo. En 1-col mostramos lista o detalle según
          // selección (mutuamente excluyentes con clases `hidden`).
          // `overflow-hidden` + `min-h-0` impiden que el grid crezca con
          // la altura intrínseca de la lista, sacando el panel detalle
          // fuera del viewport. Cada hijo hace scroll independientemente.
          "grid min-h-0 flex-1 overflow-hidden",
          "grid-cols-1 xl:grid-cols-[420px_1fr]",
        )}
      >
        <div
          className={cn(
            "flex min-h-0 flex-col",
            // En 1-col: oculta la lista cuando hay selección.
            selectedLead && "hidden xl:flex",
          )}
        >
          <LeadList
            leads={leads}
            selectedId={selectedId}
            onSelect={select}
            filterChips={filterChips}
          />
        </div>
        <div
          className={cn(
            "min-h-0",
            // En 1-col: oculta el detalle cuando NO hay selección.
            !selectedLead && "hidden xl:block",
          )}
        >
          {selectedLead ? (
            <div className="flex h-full min-h-0 flex-col">
              <button
                type="button"
                onClick={closeDetail}
                className="flex shrink-0 items-center gap-2 border-b border-wcm-detail/40 bg-wcm-primary px-4 py-2 text-xs text-wcm-text/70 hover:text-wcm-accent xl:hidden"
              >
                <span aria-hidden>←</span> Volver a la lista
              </button>
              <LeadDetailPane
                lead={selectedLead}
                sectorMedian={sectorMedian}
                percentile={percentile}
                className="flex-1"
              />
            </div>
          ) : (
            <EmptyDetail leadsCount={leads.length} stats={stats} />
          )}
        </div>
      </div>
    </div>
  );
}

function parseIdParam(raw: string | null): number | null {
  if (raw == null) return null;
  const n = Number(raw);
  return Number.isInteger(n) && n > 0 ? n : null;
}

/**
 * Construye los chips de filtro a partir del set real de leads.
 * Patrón: ordenados por frecuencia, mostramos los 5 más comunes por param
 * para no saturar visualmente. Filtros del backend (`/api/v1/leads`)
 * aceptan `sector`, `region`, `builder`, `status`.
 */
function buildFilterChips(leads: LeadRead[]): FilterChip[] {
  const buckets = {
    builder: countBy(leads, (l) => l.builder_detected ?? null),
    sector: countBy(leads, (l) => l.sector),
    region: countBy(leads, (l) => l.region),
  };
  const topN = <K extends string>(
    map: Record<string, number>,
    param: K,
    limit: number,
  ): FilterChip[] =>
    Object.entries(map)
      .sort((a, b) => b[1] - a[1])
      .slice(0, limit)
      .map(([value, count]) => ({
        id: `${param}:${value}`,
        label: value,
        count,
        param,
        value,
      }));
  return [
    ...topN(buckets.sector, "sector", 4),
    ...topN(buckets.builder, "builder", 3),
    ...topN(buckets.region, "region", 3),
  ];
}

function countBy<T>(
  items: T[],
  pick: (item: T) => string | null | undefined,
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const it of items) {
    const k = pick(it);
    if (!k || k === "unknown") continue;
    out[k] = (out[k] ?? 0) + 1;
  }
  return out;
}

/**
 * Empty state del panel detalle. Muestra agregados rápidos del set actual
 * — útil cuando aún no seleccionas nada o cuando el filtro deja 0 leads.
 */
function EmptyDetail({
  leadsCount,
  stats,
}: {
  leadsCount: number;
  stats: TopbarStatsData;
}) {
  return (
    <div className="flex items-center justify-center bg-wcm-secondary/30 p-12">
      <div className="w-full max-w-sm rounded-sm border border-wcm-detail/40 bg-wcm-primary p-8 text-center">
        <div className="text-[10.5px] font-semibold uppercase tracking-[0.1em] text-wcm-accent/80">
          Sin selección
        </div>
        <p className="mt-3 text-sm text-wcm-text/80">
          {leadsCount === 0
            ? "Ningún lead en este filtro. Limpia chips o lanza una campaña."
            : "Selecciona un lead de la lista para ver su ficha completa."}
        </p>
        {leadsCount > 0 && (
          <dl className="mt-8 grid grid-cols-2 gap-x-8 gap-y-3 text-xs">
            <Mini label="visibles">{stats.total}</Mini>
            <Mini label="sin contactar">{stats.uncontacted}</Mini>
            <Mini label="score medio">
              {stats.avgScore != null ? Math.round(stats.avgScore) : "—"}
            </Mini>
            <Mini label="builders">{stats.distinctBuilders}</Mini>
          </dl>
        )}
      </div>
    </div>
  );
}

function Mini({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-baseline justify-between gap-2 border-t border-wcm-detail/40 pt-1.5">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-semibold tabular-nums text-wcm-text">{children}</dd>
    </div>
  );
}
