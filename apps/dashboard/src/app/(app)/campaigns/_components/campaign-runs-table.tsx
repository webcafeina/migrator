import { AlertTriangle, XCircle } from "lucide-react";

import { cn, formatRelativeTime } from "@/lib/utils";

export interface CampaignRunSummary {
  id: number;
  task_id: string;
  sector: string;
  region: string;
  target_count: number;
  status: string;
  started_at: string;
  completed_at: string | null;
  duration_s: number | null;
  leads_count: number;
  warnings_count: number;
  error: string | null;
  created_by_user_id: string | null;
}

interface CampaignRunsTableProps {
  runs: CampaignRunSummary[];
  className?: string;
}

/**
 * Tabla histórica de campañas pasadas. Cada fila: fecha relativa,
 * sector·región, barra mini producidos/target, duración, status badge,
 * indicadores de warnings/error.
 *
 * Presentacional puro. El polling y filtros viven arriba (workspace
 * de /campaigns en bloque 3). Si la lista está vacía, devuelve null —
 * el padre decide qué empty state mostrar.
 */
export function CampaignRunsTable({
  runs,
  className,
}: CampaignRunsTableProps) {
  if (runs.length === 0) return null;

  return (
    <div
      className={cn(
        "overflow-hidden rounded-sm border border-wcm-detail/40",
        className,
      )}
    >
      <table className="w-full border-collapse text-[12.5px]">
        <thead className="bg-wcm-secondary/40">
          <tr>
            <Th width="120px">Lanzada</Th>
            <Th>Sector · Región</Th>
            <Th width="180px">Producidos / objetivo</Th>
            <Th width="100px">Duración</Th>
            <Th width="120px">Estado</Th>
            <Th width="80px">Avisos</Th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <Row key={r.id} run={r} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Row({ run }: { run: CampaignRunSummary }) {
  return (
    <tr className="border-t border-wcm-detail/40 transition-colors hover:bg-wcm-secondary/30">
      <td className="px-4 py-2.5 tabular-nums text-wcm-text/80">
        {formatRelativeTime(run.started_at)}
      </td>
      <td className="px-4 py-2.5 text-wcm-text">
        <span className="font-medium">{run.sector}</span>
        <span className="text-muted-foreground">{` · ${run.region}`}</span>
      </td>
      <td className="px-4 py-2.5">
        <ProducedBar leads={run.leads_count} target={run.target_count} />
      </td>
      <td className="px-4 py-2.5 tabular-nums text-wcm-text/80">
        {formatDuration(run.duration_s)}
      </td>
      <td className="px-4 py-2.5">
        <StatusBadge status={run.status} />
      </td>
      <td className="px-4 py-2.5">
        <Indicators run={run} />
      </td>
    </tr>
  );
}

function ProducedBar({ leads, target }: { leads: number; target: number }) {
  const pct = target > 0 ? Math.min(100, (leads / target) * 100) : 0;
  const ratio = `${leads}/${target}`;
  return (
    <div className="flex items-center gap-2.5">
      <div className="relative h-1.5 w-[100px] overflow-hidden rounded-[1px] bg-wcm-secondary">
        <div
          className="absolute inset-y-0 left-0 bg-wcm-accent"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="tabular-nums text-wcm-text">{ratio}</span>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; className: string }> = {
    queued: {
      label: "encolada",
      className: "border-wcm-detail/60 text-wcm-text/70",
    },
    running: {
      label: "en curso",
      className:
        "border-wcm-accent/50 bg-wcm-accent/10 text-wcm-accent",
    },
    completed: {
      label: "completada",
      className: "border-wcm-detail/60 text-wcm-text/80",
    },
    failed: {
      label: "fallida",
      className: "border-wcm-danger/40 text-wcm-danger",
    },
    cancelled: {
      label: "cancelada",
      className: "border-wcm-detail/60 text-muted-foreground",
    },
  };
  const spec = map[status] ?? {
    label: status,
    className: "border-wcm-detail/60 text-wcm-text/70",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm border px-2 py-0.5 text-[10.5px] uppercase tracking-wider",
        spec.className,
      )}
    >
      {spec.label}
    </span>
  );
}

function Indicators({ run }: { run: CampaignRunSummary }) {
  return (
    <div className="flex items-center gap-2">
      {run.warnings_count > 0 && (
        <span
          className="inline-flex items-center gap-1 text-[11px] text-wcm-warning"
          title={`${run.warnings_count} aviso(s) — ver detalle en /campaigns/runs/${run.task_id}`}
        >
          <AlertTriangle className="h-3 w-3" aria-hidden />
          <span className="tabular-nums">{run.warnings_count}</span>
        </span>
      )}
      {run.error && (
        <span
          className="inline-flex items-center gap-1 text-[11px] text-wcm-danger"
          title={run.error}
        >
          <XCircle className="h-3 w-3" aria-hidden />
          <span>error</span>
        </span>
      )}
      {run.warnings_count === 0 && !run.error && (
        <span className="text-[11px] text-muted-foreground">—</span>
      )}
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
      className="px-4 py-2 text-left text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground"
    >
      {children}
    </th>
  );
}

/**
 * Duración compacta: "—" si null, "<1m" si <60s, "Nm Ss" si <1h,
 * "Nh Mm" si >=1h. Tabular-nums-friendly.
 */
function formatDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  if (seconds < 60) return "<1m";
  const m = Math.floor(seconds / 60);
  if (m < 60) {
    const s = seconds % 60;
    return s > 0 ? `${m}m ${s}s` : `${m}m`;
  }
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return remM > 0 ? `${h}h ${remM}m` : `${h}h`;
}
