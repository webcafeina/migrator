import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import {
  CheckCircle2,
  Edit3,
  Fingerprint,
  Plus,
  Rocket,
  Search,
  Send,
  Settings2,
  Sparkles,
  Trash2,
  XCircle,
} from "lucide-react";

import { cn, formatRelativeTime } from "@/lib/utils";

export interface AuditLogEntry {
  id: string;
  at: string;
  actor: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  payload: Record<string, unknown> | null;
  legal_ground: string | null;
}

interface ActivityFeedProps {
  events: AuditLogEntry[];
  className?: string;
}

/**
 * Feed de actividad del Overview. Recibe eventos crudos del audit_log
 * (ordenados por `at` DESC desde el endpoint) y los agrupa por día.
 *
 * Encabezado de cada día: "Hoy", "Ayer", o fecha corta "Mar 17 may"
 * según proximidad. Cada evento renderiza con icono según tipo, frase
 * humana describiendo qué pasó (`describeEvent`), actor en muted y
 * tiempo relativo a la derecha.
 *
 * Si la entrada tiene `entity_type` + `entity_id`, el texto enlaza al
 * detalle correspondiente (/leads/{id}, /projects/{id}, etc.) — los
 * tipos desconocidos no enlazan.
 */
export function ActivityFeed({ events, className }: ActivityFeedProps) {
  if (events.length === 0) {
    return (
      <div className={cn("rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-8 text-center", className)}>
        <p className="text-sm text-wcm-text/70">
          Sin actividad reciente en los últimos 7 días.
        </p>
        <p className="mt-2 text-xs text-muted-foreground">
          Lanza una campaña o ejecuta una migración para ver eventos aquí.
        </p>
      </div>
    );
  }

  const groups = groupByDay(events);

  return (
    <ol className={cn("flex flex-col gap-1", className)}>
      {groups.map((group) => (
        <li key={group.dayKey} className="flex flex-col gap-0.5">
          <div className="sticky top-0 z-[1] flex items-baseline gap-3 bg-wcm-primary py-1.5 text-[10.5px] uppercase tracking-[0.1em] text-muted-foreground">
            <span>{group.label}</span>
            <span className="h-px flex-1 bg-wcm-detail/30" />
            <span className="tabular-nums">{`${group.entries.length} eventos`}</span>
          </div>
          {group.entries.map((evt) => (
            <FeedEntry key={evt.id} entry={evt} />
          ))}
        </li>
      ))}
    </ol>
  );
}

function FeedEntry({ entry }: { entry: AuditLogEntry }) {
  const Icon = iconForAction(entry.action);
  const description = describeEvent(entry);
  const href = hrefForEntity(entry.entity_type, entry.entity_id);
  const when = formatRelativeTime(entry.at);

  const inner = (
    <div className="group grid grid-cols-[20px_1fr_auto] items-baseline gap-3 px-3 py-2 transition-colors hover:bg-wcm-secondary/40">
      <Icon
        className="h-3.5 w-3.5 self-center text-muted-foreground group-hover:text-wcm-accent"
        aria-hidden
      />
      <div className="min-w-0">
        <span className="text-[13px] text-wcm-text">{description.main}</span>
        {description.detail && (
          <span className="ml-2 text-[11px] text-muted-foreground">
            {description.detail}
          </span>
        )}
        <span className="ml-2 text-[10.5px] text-muted-foreground">
          {`· ${entry.actor}`}
        </span>
      </div>
      <span className="text-[10.5px] tabular-nums text-muted-foreground">
        {when}
      </span>
    </div>
  );

  if (href) {
    return (
      <Link href={href} className="block">
        {inner}
      </Link>
    );
  }
  return inner;
}

// ---------- Agrupación ----------

interface DayGroup {
  dayKey: string;
  label: string;
  entries: AuditLogEntry[];
}

function groupByDay(events: AuditLogEntry[]): DayGroup[] {
  const map = new Map<string, AuditLogEntry[]>();
  for (const evt of events) {
    const d = new Date(evt.at);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    const arr = map.get(key) ?? [];
    arr.push(evt);
    map.set(key, arr);
  }
  return Array.from(map.entries()).map(([dayKey, entries]) => ({
    dayKey,
    label: labelForDay(dayKey),
    entries,
  }));
}

function labelForDay(dayKey: string): string {
  const [y, m, d] = dayKey.split("-").map(Number);
  const target = new Date(y!, m! - 1, d!);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  const same = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();
  if (same(target, today)) return "Hoy";
  if (same(target, yesterday)) return "Ayer";
  // "Mar 17 may" — día de semana + número + mes en es-ES.
  return target.toLocaleDateString("es-ES", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

// ---------- Descripción humana del evento ----------

interface EventDescription {
  main: string;
  detail?: string;
}

function describeEvent(entry: AuditLogEntry): EventDescription {
  const entity = entry.entity_type
    ? `${entityLabel(entry.entity_type)} #${entry.entity_id ?? "?"}`
    : "Sistema";

  switch (entry.action) {
    case "discover":
      return {
        main: `${entity} descubierto`,
        detail: extractString(entry.payload, ["url", "source"]),
      };
    case "fingerprint":
      return {
        main: `${entity} fingerprintado`,
        detail: extractString(entry.payload, ["builder", "builder_detected"]),
      };
    case "enrich":
      return {
        main: `${entity} enriquecido`,
        detail: extractString(entry.payload, ["emails_count", "summary"]),
      };
    case "send":
      return {
        main: `Outreach enviado · ${entity}`,
        detail: extractString(entry.payload, ["to", "provider_message_id"]),
      };
    case "opt_out":
      return {
        main: `${entity} marcado opt-out`,
        detail: extractString(entry.payload, ["reason", "channel"]),
      };
    case "create":
      return { main: `${entity} creado` };
    case "update":
      return { main: `${entity} actualizado` };
    case "delete":
      return { main: `${entity} eliminado` };
    case "deploy":
      return { main: `${entity} desplegado` };
    case "qa":
      return {
        main: `QA ejecutado · ${entity}`,
        detail: extractString(entry.payload, ["result", "score"]),
      };
    case "system":
      return {
        main: extractString(entry.payload, ["message", "event"]) ?? "Evento de sistema",
      };
    default:
      return { main: `${entry.action} · ${entity}` };
  }
}

function entityLabel(entityType: string): string {
  const map: Record<string, string> = {
    lead: "Lead",
    project: "Proyecto",
    campaign: "Campaña",
    outreach_sequence: "Secuencia outreach",
    outreach_send: "Envío",
    residual_task: "Tarea residual",
    user: "Usuario",
  };
  return map[entityType] ?? entityType;
}

function hrefForEntity(
  entityType: string | null,
  entityId: string | null,
): string | null {
  if (!entityType || !entityId) return null;
  switch (entityType) {
    case "lead":
      return `/leads?selected=${entityId}`;
    case "project":
      return `/projects/${entityId}`;
    case "residual_task":
      return "/residual-tasks";
    default:
      return null;
  }
}

function iconForAction(action: string): LucideIcon {
  switch (action) {
    case "discover":
      return Search;
    case "fingerprint":
      return Fingerprint;
    case "enrich":
      return Sparkles;
    case "send":
      return Send;
    case "opt_out":
      return XCircle;
    case "create":
      return Plus;
    case "update":
      return Edit3;
    case "delete":
      return Trash2;
    case "deploy":
      return Rocket;
    case "qa":
      return CheckCircle2;
    case "system":
    default:
      return Settings2;
  }
}

function extractString(
  payload: Record<string, unknown> | null,
  keys: string[],
): string | undefined {
  if (!payload) return undefined;
  for (const k of keys) {
    const v = payload[k];
    if (typeof v === "string" && v.length > 0) return v;
    if (typeof v === "number") return String(v);
  }
  return undefined;
}
