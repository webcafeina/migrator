import Link from "next/link";

import { api } from "@/lib/api";
import { cn, formatRelativeTime } from "@/lib/utils";

interface AuditEntry {
  id: string;
  at: string;
  actor: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  payload: Record<string, unknown> | null;
  legal_ground: string | null;
}

interface SearchParams {
  action?: string;
  entity_type?: string;
  actor?: string;
  /** ISO datetime; el backend default = últimos 7 días. */
  since?: string;
  limit?: string;
}

/**
 * `/audit-log` — vista completa con filtros del audit_log. Sustituye
 * el feed mini de 5 entradas del homepage para compliance/debugging
 * serio. RBAC any_user (lectura abierta a operadores y viewers).
 */
export default async function AuditLogPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const apiParams: Record<string, string | number> = {
    limit: Number(params.limit ?? 100),
  };
  if (params.action) apiParams.action = params.action;
  if (params.entity_type) apiParams.entity_type = params.entity_type;
  if (params.actor) apiParams.actor = params.actor;
  if (params.since) apiParams.since = params.since;

  const entries = await api
    .get<AuditEntry[]>("/api/v1/audit-log", { searchParams: apiParams })
    .catch(() => [] as AuditEntry[]);

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold text-wcm-text">Audit log</h1>
          <p className="text-xs text-muted-foreground">
            Vista completa con filtros para compliance RGPD y
            debugging. Por defecto últimos 7 días, máx 100 entradas
            (subir <code>?limit=200</code>).
          </p>
        </div>
        <Link
          href="/"
          className="text-xs text-wcm-text/70 hover:text-wcm-accent"
        >
          ← Panel
        </Link>
      </header>

      {/* Filtros */}
      <Filters params={params} />

      {/* Tabla */}
      {entries.length === 0 ? (
        <div className="rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-6 text-center text-xs text-muted-foreground">
          Sin entradas que coincidan con los filtros (o el rango está
          vacío). Prueba quitar filtros.
        </div>
      ) : (
        <div className="overflow-hidden rounded-sm border border-wcm-detail/40">
          <table className="w-full border-collapse text-[11.5px]">
            <thead className="bg-wcm-secondary/40">
              <tr>
                <Th width="120px">Cuándo</Th>
                <Th width="100px">Acción</Th>
                <Th width="100px">Entidad</Th>
                <Th width="80px">ID</Th>
                <Th>Actor</Th>
                <Th>Detalles</Th>
                <Th width="80px">Base legal</Th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <Row key={e.id} entry={e} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-[10.5px] text-muted-foreground">
        {`${entries.length} entrada${entries.length === 1 ? "" : "s"} mostradas`}
        {params.action || params.entity_type || params.actor || params.since
          ? " · filtros activos"
          : " · sin filtros (últimos 7 días)"}
      </p>
    </div>
  );
}

function Filters({ params }: { params: SearchParams }) {
  return (
    <form
      method="get"
      className="grid grid-cols-1 gap-3 rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-3 text-xs sm:grid-cols-5"
    >
      <FilterField label="Acción" name="action" value={params.action}>
        <option value="">— Todas —</option>
        <option value="discover">discover</option>
        <option value="update">update</option>
        <option value="enrich">enrich</option>
        <option value="fingerprint">fingerprint</option>
        <option value="compose">compose</option>
        <option value="send">send</option>
        <option value="opt_out">opt_out</option>
        <option value="delete">delete</option>
        <option value="create">create</option>
      </FilterField>
      <FilterField
        label="Entidad"
        name="entity_type"
        value={params.entity_type}
      >
        <option value="">— Todas —</option>
        <option value="lead">lead</option>
        <option value="project">project</option>
        <option value="campaign">campaign</option>
        <option value="outreach_sequence">outreach_sequence</option>
        <option value="outreach_send">outreach_send</option>
        <option value="user">user</option>
      </FilterField>
      <FilterFieldText label="Actor" name="actor" value={params.actor} placeholder="user:UUID o agent:name" />
      <FilterFieldText
        label="Desde (ISO)"
        name="since"
        value={params.since}
        placeholder="2026-05-01T00:00:00Z"
      />
      <div className="flex items-end gap-2">
        <button
          type="submit"
          className="h-8 rounded-sm bg-wcm-accent px-3 text-xs font-semibold text-wcm-primary hover:brightness-105"
        >
          Filtrar →
        </button>
        <Link
          href="/audit-log"
          className="h-8 rounded-sm border border-wcm-detail/60 px-3 py-1.5 text-xs text-wcm-text/80 hover:border-wcm-detail"
        >
          Limpiar
        </Link>
      </div>
    </form>
  );
}

function FilterField({
  label,
  name,
  value,
  children,
}: {
  label: string;
  name: string;
  value?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
        {label}
      </span>
      <select
        name={name}
        defaultValue={value ?? ""}
        className="h-8 rounded-sm border border-wcm-detail/70 bg-wcm-primary px-2 text-xs text-wcm-text focus:border-wcm-accent focus:outline-none"
      >
        {children}
      </select>
    </label>
  );
}

function FilterFieldText({
  label,
  name,
  value,
  placeholder,
}: {
  label: string;
  name: string;
  value?: string;
  placeholder?: string;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
        {label}
      </span>
      <input
        name={name}
        defaultValue={value ?? ""}
        placeholder={placeholder}
        className="h-8 rounded-sm border border-wcm-detail/70 bg-wcm-primary px-2 text-xs text-wcm-text placeholder:text-muted-foreground focus:border-wcm-accent focus:outline-none"
      />
    </label>
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

function Row({ entry }: { entry: AuditEntry }) {
  return (
    <tr className="border-t border-wcm-detail/40 hover:bg-wcm-secondary/30">
      <td
        className="px-3 py-2 tabular-nums text-wcm-text/70"
        title={entry.at}
      >
        {formatRelativeTime(entry.at)}
      </td>
      <td className="px-3 py-2">
        <ActionBadge action={entry.action} />
      </td>
      <td className="px-3 py-2 text-wcm-text/80">
        {entry.entity_type ?? "—"}
      </td>
      <td className="px-3 py-2 tabular-nums text-wcm-text/70">
        {entry.entity_id ?? "—"}
      </td>
      <td className="px-3 py-2 font-mono text-[10.5px] text-wcm-text/80">
        {entry.actor}
      </td>
      <td className="px-3 py-2">
        <PayloadCell payload={entry.payload} />
      </td>
      <td className="px-3 py-2 text-[10.5px] text-muted-foreground">
        {entry.legal_ground ?? "—"}
      </td>
    </tr>
  );
}

function ActionBadge({ action }: { action: string }) {
  const map: Record<string, string> = {
    discover: "border-wcm-detail/60 text-wcm-text/80",
    update: "border-wcm-detail/60 text-wcm-text/80",
    enrich: "border-wcm-accent/40 text-wcm-accent",
    fingerprint: "border-wcm-accent/40 text-wcm-accent",
    compose: "border-wcm-accent/40 text-wcm-accent",
    send: "border-wcm-accent/50 bg-wcm-accent/10 text-wcm-accent",
    opt_out: "border-wcm-warning/50 text-wcm-warning",
    delete: "border-wcm-danger/50 bg-wcm-danger/10 text-wcm-danger",
    create: "border-wcm-accent/40 text-wcm-accent",
  };
  const cls = map[action] ?? "border-wcm-detail/60 text-wcm-text/70";
  return (
    <span
      className={cn(
        "inline-flex rounded-sm border px-1.5 py-0.5 text-[10px] uppercase tracking-wider",
        cls,
      )}
    >
      {action}
    </span>
  );
}

function PayloadCell({
  payload,
}: {
  payload: Record<string, unknown> | null;
}) {
  if (!payload || Object.keys(payload).length === 0) {
    return <span className="text-muted-foreground">—</span>;
  }
  // Mostrar los 3 primeros pares clave:valor inline; el resto con
  // hover para expandir vía title (JSON pretty).
  const entries = Object.entries(payload).slice(0, 3);
  const moreCount = Object.keys(payload).length - entries.length;
  return (
    <span
      className="text-[11px] text-wcm-text/80"
      title={JSON.stringify(payload, null, 2)}
    >
      {entries.map(([k, v]) => (
        <span key={k} className="mr-2">
          <span className="text-muted-foreground">{k}=</span>
          <span className="text-wcm-text/90">
            {typeof v === "string"
              ? v.length > 30
                ? v.slice(0, 30) + "…"
                : v
              : JSON.stringify(v)}
          </span>
        </span>
      ))}
      {moreCount > 0 && (
        <span className="text-muted-foreground">+{moreCount} más</span>
      )}
    </span>
  );
}
