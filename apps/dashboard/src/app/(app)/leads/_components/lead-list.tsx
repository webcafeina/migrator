"use client";

import Link from "next/link";

import { cn, formatRelativeTime } from "@/lib/utils";
import type { LeadRead } from "@/types/api";

import { FilterChips, type FilterChip } from "@/components/filter-chips";

interface LeadListProps {
  leads: LeadRead[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  /** Chips de filtro derivados del set de leads (los pasa el workspace). */
  filterChips: FilterChip[];
  className?: string;
}

const UNCONTACTED = new Set([
  "discovered",
  "fingerprinted",
  "enriched",
]);

/**
 * Lista master del master-detail. Agrupa por "sin contactar" vs
 * "procesados", ordena por score DESC dentro de cada grupo, y resalta
 * el lead seleccionado con borde lima a la izquierda.
 *
 * Click en una fila llama `onSelect(id)` que el workspace traduce a
 * `router.replace(?selected=N)`. La selección es local-instant: no
 * re-fetch.
 */
export function LeadList({
  leads,
  selectedId,
  onSelect,
  filterChips,
  className,
}: LeadListProps) {
  const uncontacted = leads
    .filter((l) => UNCONTACTED.has(l.status))
    .sort((a, b) => b.score - a.score);
  const processed = leads
    .filter((l) => !UNCONTACTED.has(l.status))
    .sort((a, b) => b.score - a.score);

  return (
    <section
      className={cn(
        // `min-h-0` necesario para que el `<ol>` interno con `overflow-y-auto`
        // pueda scrollear dentro del grid padre (CSS Grid + flex).
        "flex min-h-0 flex-col border-r border-wcm-detail/40 bg-wcm-primary",
        className,
      )}
    >
      <header className="flex shrink-0 flex-col gap-2.5 border-b border-wcm-detail/40 bg-wcm-primary px-4 pt-3.5 pb-2">
        <div className="flex items-baseline gap-2.5">
          <h1 className="text-base font-bold tracking-tight">Leads</h1>
          <span className="text-[10.5px] uppercase tracking-[0.08em] text-muted-foreground tabular-nums">
            {`${leads.length} resultados`}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex flex-1 items-center gap-1.5 rounded-sm border border-wcm-detail/70 bg-wcm-secondary px-2 py-1 text-xs text-muted-foreground hover:border-muted-foreground">
            <SearchIcon />
            <span>Buscar empresa, URL, sector…</span>
            <span className="ml-auto rounded-sm border border-wcm-detail px-1.5 py-px text-[10.5px] text-muted-foreground">
              ⌘K
            </span>
          </div>
          <Link
            href="/leads/new"
            className="rounded-sm border border-wcm-detail/60 px-2.5 py-1 text-xs text-wcm-text/90 transition-colors hover:border-wcm-accent hover:text-wcm-accent"
            title="Añadir URLs concretas a evaluar (sin campaña)"
          >
            + Nuevo lead
          </Link>
          <Link
            href="/campaigns"
            className="rounded-sm bg-wcm-accent px-2.5 py-1 text-xs font-semibold text-wcm-primary hover:brightness-105"
          >
            + Lanzar campaña
          </Link>
        </div>

        <FilterChips chips={filterChips} />

        <div className="text-[10.5px] tracking-wide text-muted-foreground">
          {"orden · "}
          <strong className="font-semibold text-wcm-text">score ↓</strong>
          {" · sin contactar primero"}
        </div>
      </header>

      <ol className="min-h-0 flex-1 overflow-y-auto" aria-label="Lista de leads">
        {uncontacted.length > 0 && (
          <GroupSep label="Sin contactar" count={uncontacted.length} />
        )}
        {uncontacted.map((l) => (
          <ListItem
            key={l.id}
            lead={l}
            warm
            selected={l.id === selectedId}
            onSelect={onSelect}
          />
        ))}

        {processed.length > 0 && (
          <GroupSep label="Procesados" count={processed.length} />
        )}
        {processed.map((l) => (
          <ListItem
            key={l.id}
            lead={l}
            warm={false}
            selected={l.id === selectedId}
            onSelect={onSelect}
          />
        ))}

        {leads.length === 0 && (
          <li className="px-4 py-10 text-center text-xs text-muted-foreground">
            Sin leads con estos filtros. Limpia filtros o lanza una campaña
            desde <span className="text-wcm-accent">+ Lanzar campaña</span>.
          </li>
        )}
      </ol>

      <footer className="flex shrink-0 gap-3 border-t border-wcm-detail/40 px-4 py-2.5 text-[10.5px] text-muted-foreground">
        <Kbd label="↑↓" /> navegar
        <Kbd label="↵" /> abrir
        <Kbd label="c" /> componer
        <Kbd label="x" /> descartar
      </footer>
    </section>
  );
}

// ---------- Helpers internos ----------

function ListItem({
  lead,
  warm,
  selected,
  onSelect,
}: {
  lead: LeadRead;
  warm: boolean;
  selected: boolean;
  onSelect: (id: number) => void;
}) {
  const display =
    lead.business_name ??
    (typeof lead.url === "string" ? lead.url : String(lead.url));
  const builder = lead.builder_detected ?? null;
  const when = formatRelativeTime(
    lead.last_crawl_at ?? lead.updated_at ?? lead.created_at,
  );

  return (
    <li
      role="button"
      tabIndex={0}
      aria-current={selected ? "true" : "false"}
      onClick={() => onSelect(lead.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(lead.id);
        }
      }}
      className={cn(
        "relative grid cursor-pointer grid-cols-[36px_1fr_auto] gap-2.5 border-b border-wcm-detail/40 px-4 py-2.5 transition-colors hover:bg-wcm-secondary/70",
        selected && "bg-wcm-secondary",
        warm ? "" : "opacity-90",
      )}
    >
      {selected && (
        <span
          aria-hidden
          className="absolute inset-y-0 left-0 w-[2px] bg-wcm-accent"
        />
      )}

      <div className="flex items-center gap-1.5 pt-0.5">
        <span
          className={cn(
            "h-[7px] w-[7px] shrink-0 rounded-full",
            warm
              ? "bg-wcm-accent shadow-[0_0_0_2px_rgba(177,241,0,0.15)]"
              : "border border-wcm-detail bg-transparent",
          )}
        />
        <span
          className={cn(
            "text-sm font-semibold tabular-nums",
            warm ? "text-wcm-text" : "text-muted-foreground",
          )}
        >
          {lead.score}
        </span>
      </div>

      <div className="min-w-0">
        <div
          className={cn(
            "truncate text-[13px] font-medium",
            warm ? "text-wcm-text" : "text-wcm-text/70",
          )}
        >
          {display}
        </div>
        <div className="mt-0.5 flex gap-2 text-[11px] text-muted-foreground">
          <span>{lead.sector ?? "—"}</span>
          <span aria-hidden>·</span>
          <span>{lead.region ?? "—"}</span>
          <span aria-hidden>·</span>
          <span
            className={cn(
              builder && builder !== "unknown"
                ? "text-wcm-text/70"
                : "text-muted-foreground",
            )}
          >
            {builder ?? "—"}
          </span>
        </div>
      </div>

      <div className="self-start pt-1 text-[10.5px] tabular-nums text-muted-foreground">
        {when}
      </div>
    </li>
  );
}

function GroupSep({ label, count }: { label: string; count: number }) {
  return (
    <li
      aria-hidden
      className="border-b border-wcm-detail/40 bg-wcm-primary px-4 pb-1.5 pt-2 text-[10px] uppercase tracking-[0.1em] text-muted-foreground"
    >
      {`${label} · ${count}`}
    </li>
  );
}

function Kbd({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center rounded-sm border border-wcm-detail px-1.5 py-px text-[10.5px] text-muted-foreground">
      {label}
    </span>
  );
}

function SearchIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      aria-hidden
    >
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}
