import Link from "next/link";

import { api } from "@/lib/api";
import type { LeadRead } from "@/types/api";

import { LeadCreateForm } from "./lead-create-form";

/**
 * `/leads/new` — alta manual de leads (single + bulk).
 *
 * Server Component. Fetcha `/api/v1/leads?limit=200` con `.catch()`
 * defensivo solo para extraer sector/region únicos del set actual y
 * alimentar los datalist del form (autocompletado, no obligatorio).
 *
 * Si en algún momento la BD crece y los 200 leads no son suficientes
 * para suggestions útiles, refactorizar a endpoint dedicado
 * `/api/v1/leads/suggestions` (no urgente con <500 leads).
 */
export default async function NewLeadPage() {
  const recent = await api
    .get<LeadRead[]>("/api/v1/leads", { searchParams: { limit: 200 } })
    .catch(() => [] as LeadRead[]);

  const sectorSuggestions = uniqueByFrequency(
    recent.map((l) => l.sector ?? "").filter(Boolean),
  );
  const regionSuggestions = uniqueByFrequency(
    recent.map((l) => l.region ?? "").filter(Boolean),
  );

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold text-wcm-text">Nuevo lead</h1>
          <p className="text-xs text-muted-foreground">
            Añade URLs concretas a evaluar sin lanzar una campaña. Tras
            crear, el sistema dispara fingerprint + enrich
            automáticamente.
          </p>
        </div>
        <Link
          href="/leads"
          className="text-xs text-wcm-text/70 hover:text-wcm-accent"
        >
          ← Volver a la lista
        </Link>
      </header>

      <section className="rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-4">
        <LeadCreateForm
          sectorSuggestions={sectorSuggestions}
          regionSuggestions={regionSuggestions}
        />
      </section>

      <p className="text-[10.5px] text-muted-foreground">
        Trazabilidad RGPD: cada lead manual queda registrado en{" "}
        <code>audit_log</code> con base jurídica art. 6.1.f (interés
        legítimo B2B, igual que la prospección automática) y{" "}
        <code>payload.source</code> distingue la procedencia
        (<code>manual_single</code> /{" "}
        <code>manual_bulk</code>).
      </p>
    </div>
  );
}

/**
 * Ordena strings por frecuencia descendente, dedup, top 20. Útil para
 * datalists de sugerencias — los más comunes primero ayudan a evitar
 * typos del operador.
 */
function uniqueByFrequency(values: string[]): string[] {
  const counts = new Map<string, number>();
  for (const v of values) {
    counts.set(v, (counts.get(v) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 20)
    .map(([v]) => v);
}
