import Link from "next/link";

import { FilterChips, type FilterChip } from "@/components/filter-chips";
import { KpiStrip, type Kpi } from "@/components/kpi-strip";
import { api } from "@/lib/api";
import { sequenceStatusLabel } from "@/lib/labels";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { LeadRead, OutreachSequenceRead } from "@/types/api";

interface SearchParams {
  status?: string;
}

const STATUS_CHIPS_SOURCE = [
  ["draft_pending_review", "Borrador pendiente"],
  ["ready", "Lista para enviar"],
  ["in_progress", "Enviando"],
  ["paused", "Pausada"],
  ["completed", "Completada"],
] as const;

/**
 * `/contactos` — vista global cross-lead de todas las secuencias de
 * contacto comercial. Útil para "qué tengo pendiente de aprobar/
 * enviar" sin recorrer leads uno a uno.
 *
 * Click en una fila navega al lead detail con anchor #outreach.
 */
export default async function ContactosPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const sequences = await api
    .get<OutreachSequenceRead[]>("/api/v1/outreach/sequences", {
      searchParams: params.status
        ? { status: params.status, limit: 200 }
        : { limit: 200 },
    })
    .catch(() => [] as OutreachSequenceRead[]);

  // Resolver business_name de cada lead para mostrarlo. Fetch en
  // paralelo de los leads únicos referenciados.
  const uniqueLeadIds = Array.from(new Set(sequences.map((s) => s.lead_id)));
  const leadMap = new Map<number, LeadRead>();
  await Promise.all(
    uniqueLeadIds.map(async (id) => {
      try {
        const lead = await api.get<LeadRead>(`/api/v1/leads/${id}`);
        leadMap.set(id, lead);
      } catch {
        /* lead borrado o sin acceso — fila quedará con "lead #N" */
      }
    }),
  );

  // Counts por status para chips + KpiStrip.
  const counts = sequences.reduce<Record<string, number>>((acc, s) => {
    const k = String(s.status).toLowerCase();
    acc[k] = (acc[k] ?? 0) + 1;
    return acc;
  }, {});

  const kpis: Kpi[] = [
    { label: "Total", value: sequences.length },
    {
      label: "Borrador pendiente",
      value: counts["draft_pending_review"] ?? 0,
      accent: (counts["draft_pending_review"] ?? 0) > 0,
    },
    {
      label: "Lista para enviar",
      value: counts["ready"] ?? 0,
      accent: (counts["ready"] ?? 0) > 0,
    },
    { label: "Enviando", value: counts["in_progress"] ?? 0 },
    { label: "Completadas", value: counts["completed"] ?? 0 },
  ];

  const chips: FilterChip[] = STATUS_CHIPS_SOURCE.map(([value, label]) => ({
    id: `status:${value}`,
    label,
    count: counts[value] ?? 0,
    param: "status",
    value,
  }));

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold text-wcm-text">
            Contacto comercial
          </h1>
          <p className="text-xs text-muted-foreground">
            Vista global de todas las secuencias generadas. Sequence
            por lead típicamente; click en una fila abre la ficha del
            lead con el panel de contacto.
          </p>
        </div>
      </header>

      <KpiStrip kpis={kpis} />

      <section className="space-y-3">
        <header className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            Listado
          </h2>
          <span className="text-[10.5px] tabular-nums text-muted-foreground">
            {`${sequences.length} resultado${sequences.length === 1 ? "" : "s"}`}
            {params.status
              ? ` · filtrado por ${sequenceStatusLabel(params.status)}`
              : ""}
          </span>
        </header>

        {sequences.length > 0 && <FilterChips chips={chips} />}

        {sequences.length === 0 ? (
          <Empty hasFilter={!!params.status} />
        ) : (
          <SequencesTable sequences={sequences} leadMap={leadMap} />
        )}
      </section>
    </div>
  );
}

function Empty({ hasFilter }: { hasFilter: boolean }) {
  if (hasFilter) {
    return (
      <div className="rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-6 text-center text-xs text-muted-foreground">
        Sin secuencias con este filtro de estado.
      </div>
    );
  }
  return (
    <div className="rounded-sm border border-wcm-accent/30 bg-wcm-accent/[0.04] p-6">
      <div className="text-[10.5px] font-semibold uppercase tracking-[0.1em] text-wcm-accent">
        Sin contactos generados
      </div>
      <p className="mt-2 text-sm text-wcm-text/80">
        Aún no se ha compuesto ningún borrador de contacto.
      </p>
      <p className="mt-2 text-xs text-muted-foreground">
        Para generar el primero: abre un lead en{" "}
        <Link href="/leads" className="text-wcm-accent hover:underline">
          /leads
        </Link>
        , pulsa <strong>Componer contacto →</strong> en la barra de
        acciones y vuelve aquí.
      </p>
    </div>
  );
}

function SequencesTable({
  sequences,
  leadMap,
}: {
  sequences: OutreachSequenceRead[];
  leadMap: Map<number, LeadRead>;
}) {
  return (
    <div className="overflow-hidden rounded-sm border border-wcm-detail/40">
      <table className="w-full border-collapse text-xs">
        <thead className="bg-wcm-secondary/40">
          <tr>
            <Th width="60px">Lead</Th>
            <Th>Negocio</Th>
            <Th>Plantilla</Th>
            <Th width="160px">Estado</Th>
            <Th width="80px">Legal</Th>
            <Th width="120px">Creada</Th>
            <Th width="100px"> </Th>
          </tr>
        </thead>
        <tbody>
          {sequences.map((s) => {
            const lead = leadMap.get(s.lead_id);
            return (
              <tr
                key={s.id}
                className="border-t border-wcm-detail/40 hover:bg-wcm-secondary/30"
              >
                <td className="px-3 py-2 tabular-nums text-wcm-text/80">
                  #{s.lead_id}
                </td>
                <td className="px-3 py-2">
                  {lead ? (
                    <div>
                      <div className="font-semibold text-wcm-text">
                        {lead.business_name ?? lead.url}
                      </div>
                      <div className="text-[10.5px] text-muted-foreground">
                        {lead.url}
                      </div>
                    </div>
                  ) : (
                    <span className="text-muted-foreground">
                      lead borrado o sin acceso
                    </span>
                  )}
                </td>
                <td className="px-3 py-2">
                  <code className="text-[11px] text-wcm-text/80">
                    {s.template_name}
                  </code>
                </td>
                <td className="px-3 py-2">
                  <SequenceStatusBadge status={String(s.status)} />
                </td>
                <td className="px-3 py-2 text-center">
                  {s.legal_validation_passed ? (
                    <span className="text-wcm-accent">✓</span>
                  ) : (
                    <span className="text-wcm-danger">✗</span>
                  )}
                </td>
                <td className="px-3 py-2 tabular-nums text-wcm-text/70">
                  {formatRelativeTime(s.created_at)}
                </td>
                <td className="px-3 py-2 text-right">
                  <Link
                    href={`/leads?selected=${s.lead_id}#outreach`}
                    className="rounded-sm border border-wcm-detail/60 px-2 py-0.5 text-[10.5px] text-wcm-text hover:border-wcm-accent hover:text-wcm-accent"
                  >
                    Abrir →
                  </Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Th({
  children,
  width,
}: {
  children: React.ReactNode;
  width?: string;
}) {
  return (
    <th
      style={width ? { width } : undefined}
      className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground"
    >
      {children}
    </th>
  );
}

function SequenceStatusBadge({ status }: { status: string }) {
  const upper = status.toUpperCase();
  const map: Record<string, string> = {
    DRAFT_PENDING_REVIEW:
      "border-wcm-warning/50 bg-wcm-warning/10 text-wcm-warning",
    READY: "border-wcm-accent/50 bg-wcm-accent/10 text-wcm-accent",
    IN_PROGRESS:
      "border-wcm-accent/50 bg-wcm-accent/10 text-wcm-accent",
    COMPLETED: "border-wcm-detail/60 text-wcm-text/80",
    PAUSED: "border-wcm-warning/40 text-wcm-warning",
    CANCELLED: "border-wcm-danger/40 text-wcm-danger",
    OPTED_OUT: "border-wcm-danger/40 text-wcm-danger",
  };
  const cls = map[upper] ?? "border-wcm-detail/60 text-wcm-text/70";
  return (
    <span
      className={cn(
        "inline-flex rounded-sm border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
        cls,
      )}
    >
      {sequenceStatusLabel(status)}
    </span>
  );
}
