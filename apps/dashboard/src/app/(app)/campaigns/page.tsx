import { api } from "@/lib/api";

import {
  CampaignRunsTable,
  type CampaignRunSummary,
} from "./_components/campaign-runs-table";
import { CampaignProgressCard } from "./_components/campaign-progress-card";
import { LaunchCampaignForm } from "./launch-form";

/**
 * `/campaigns` — rediseño 3-zona vertical (ADR diseño 2026-05-18):
 *
 * 1. **Lanzar** (arriba): form compacto en una línea + microcopy legal.
 * 2. **En curso** (medio): `CampaignProgressCard` auto-oculta si no hay.
 * 3. **Histórico** (abajo): tabla paginada de runs pasadas, derivada
 *    del nuevo endpoint `/api/v1/campaigns/runs`.
 *
 * Fetch único en server (runs). Las activas se polea desde el Client
 * (CampaignProgressCard) cada 5s. Las sugerencias del form vienen del
 * propio histórico — autocompletar con sectores/regiones ya usados.
 */
export default async function CampaignsPage() {
  const runs = await api
    .get<CampaignRunSummary[]>("/api/v1/campaigns/runs", {
      searchParams: { limit: 50 },
    })
    .catch(() => [] as CampaignRunSummary[]);

  const sectorSuggestions = uniqueByFrequency(runs.map((r) => r.sector));
  const regionSuggestions = uniqueByFrequency(runs.map((r) => r.region));

  return (
    <div className="space-y-5">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-lg font-semibold text-wcm-text">
            Campañas de prospección
          </h1>
          <p className="text-xs text-muted-foreground">
            Lanza, sigue el progreso en curso y revisa el histórico de
            campañas pasadas.
          </p>
        </div>
      </header>

      <section className="rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-4">
        <LaunchCampaignForm
          sectorSuggestions={sectorSuggestions}
          regionSuggestions={regionSuggestions}
        />
        <p className="mt-3 text-[11px] text-muted-foreground">
          El sistema <span className="text-wcm-text">nunca</span> envía
          outreach automáticamente. La campaña descubre y enriquece leads
          vía Google Places + dorks; la aprobación del outreach es manual
          desde cada ficha de lead.
        </p>
      </section>

      <CampaignProgressCard />

      <section className="space-y-3">
        <header className="flex items-baseline justify-between">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            Histórico de campañas
          </h2>
          <span className="text-[10.5px] tabular-nums text-muted-foreground">
            {`${runs.length} resultado${runs.length === 1 ? "" : "s"} · últimos 30 días`}
          </span>
        </header>
        {runs.length === 0 ? (
          <EmptyHistorico />
        ) : (
          <CampaignRunsTable runs={runs} />
        )}
      </section>
    </div>
  );
}

/**
 * Devuelve valores únicos ordenados por frecuencia descendente. Útil
 * para alimentar el `<datalist>` del form con los sectores/regiones más
 * usados primero.
 */
function uniqueByFrequency(values: string[]): string[] {
  const counts = new Map<string, number>();
  for (const v of values) {
    if (!v) continue;
    counts.set(v, (counts.get(v) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([v]) => v);
}

function EmptyHistorico() {
  return (
    <div className="rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-6 text-center">
      <p className="text-sm text-wcm-text/70">
        Sin campañas en los últimos 30 días.
      </p>
      <p className="mt-2 text-xs text-muted-foreground">
        Lanza tu primera campaña arriba — una campaña típica produce 30-60
        leads cualificados por sector + región en menos de 1 hora.
      </p>
    </div>
  );
}
