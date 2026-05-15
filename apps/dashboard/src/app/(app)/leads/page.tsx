import { api } from "@/lib/api";
import type { LeadRead } from "@/types/api";

import { LeadsWorkspace } from "./_components/leads-workspace";
import type { TopbarStatsData } from "./_components/topbar-stats";

interface SearchParams {
  sector?: string;
  region?: string;
  builder?: string;
  status?: string;
  min_score?: string;
  /** ID del lead seleccionado en el panel detalle. Lo gestiona el workspace. */
  selected?: string;
}

interface LeadStatsResponse {
  total: number;
  uncontacted: number;
  avg_score: number | null;
  distinct_builders: number;
  distinct_sectors: number;
  distinct_regions: number;
}

/**
 * `/leads` — vista master-detail (ADR diseño rediseño 2026-05-15).
 *
 * Server Component: fetcha en paralelo `/api/v1/leads` (lista filtrada
 * por los chips presentes en searchParams) y `/api/v1/leads/stats`
 * (agregados globales para topbar y empty state). Pasa todo a
 * `LeadsWorkspace` (Client) que gestiona la selección reactiva por URL
 * sin re-fetch.
 *
 * `selected` y demás searchParams se mantienen sincronizados desde el
 * cliente vía `router.replace(?...)`.
 */
export default async function LeadsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const [leads, stats] = await Promise.all([
    api
      .get<LeadRead[]>("/api/v1/leads", {
        searchParams: {
          sector: params.sector,
          region: params.region,
          builder: params.builder,
          status: params.status,
          min_score: params.min_score ?? "0",
          limit: 200,
        },
      })
      .catch(() => [] as LeadRead[]),
    api
      .get<LeadStatsResponse>("/api/v1/leads/stats")
      .catch(
        () =>
          ({
            total: 0,
            uncontacted: 0,
            avg_score: null,
            distinct_builders: 0,
            distinct_sectors: 0,
            distinct_regions: 0,
          }) satisfies LeadStatsResponse,
      ),
  ]);

  const topbarStats: TopbarStatsData = {
    total: stats.total,
    uncontacted: stats.uncontacted,
    avgScore: stats.avg_score,
    distinctBuilders: stats.distinct_builders,
  };

  return (
    <LeadsWorkspace
      leads={leads}
      stats={topbarStats}
      sectorMedians={computeSectorMedians(leads)}
    />
  );
}

/**
 * Mediana del score por sector dentro del set actual de leads. Server-side
 * para ahorrar trabajo al cliente. Para datasets grandes (>1k) habría que
 * mover esto a un endpoint dedicado con GROUP BY en SQL.
 */
function computeSectorMedians(leads: LeadRead[]): Record<string, number> {
  const bySector = new Map<string, number[]>();
  for (const lead of leads) {
    if (!lead.sector || lead.score <= 0) continue;
    const arr = bySector.get(lead.sector) ?? [];
    arr.push(lead.score);
    bySector.set(lead.sector, arr);
  }
  const out: Record<string, number> = {};
  for (const [sector, scores] of bySector) {
    scores.sort((a, b) => a - b);
    const mid = Math.floor(scores.length / 2);
    out[sector] =
      scores.length % 2 === 0
        ? Math.round((scores[mid - 1]! + scores[mid]!) / 2)
        : scores[mid]!;
  }
  return out;
}
