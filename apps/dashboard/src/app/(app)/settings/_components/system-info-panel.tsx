import { cn } from "@/lib/utils";

export interface SystemInfoData {
  version: string;
  environment: string;
  python_version: string;
  alembic_revision: string | null;
  uptime_seconds: number;
  health: {
    overall: "ok" | "degraded" | "fail";
    db: "ok" | "fail" | "skipped";
    redis: "ok" | "fail" | "skipped";
    r2: "ok" | "fail" | "skipped";
  };
}

interface SystemInfoPanelProps {
  info: SystemInfoData | null;
}

/**
 * Runtime info del API: version, environment, alembic revision, uptime
 * y resumen de health. Estructura kv-densa idéntica a `UserCard`. El
 * health summary aparece como sub-bloque con dots de color por dep.
 */
export function SystemInfoPanel({ info }: SystemInfoPanelProps) {
  if (!info) {
    return (
      <div className="rounded-sm border border-wcm-danger/40 bg-wcm-danger/[0.05] p-4 text-xs text-wcm-text/80">
        El API no responde. Comprueba <code>systemctl status
        webcafeina-api</code> en el servidor.
      </div>
    );
  }

  const rows: Array<[string, React.ReactNode]> = [
    ["versión", <code key="v" className="text-wcm-text">{info.version}</code>],
    ["entorno", <EnvBadge key="e" env={info.environment} />],
    ["python", info.python_version],
    [
      "alembic",
      info.alembic_revision ? (
        <code className="text-wcm-text">{info.alembic_revision}</code>
      ) : (
        <span className="text-muted-foreground">
          sin migraciones aplicadas
        </span>
      ),
    ],
    ["uptime", formatUptime(info.uptime_seconds)],
  ];

  return (
    <div className="space-y-3 rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-4 text-xs">
      <dl className="grid grid-cols-[80px_1fr] gap-x-3 gap-y-2">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-muted-foreground">{k}</dt>
            <dd className="break-all text-wcm-text">{v}</dd>
          </div>
        ))}
      </dl>

      <div className="space-y-1.5 border-t border-wcm-detail/30 pt-3">
        <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
          <span>health</span>
          <OverallBadge overall={info.health.overall} />
        </div>
        <ul className="space-y-1">
          <HealthRow label="postgres" status={info.health.db} />
          <HealthRow label="redis" status={info.health.redis} />
          <HealthRow
            label="r2"
            status={info.health.r2}
            note={info.health.r2 === "skipped" ? "(opcional)" : undefined}
          />
        </ul>
      </div>
    </div>
  );
}

function HealthRow({
  label,
  status,
  note,
}: {
  label: string;
  status: "ok" | "fail" | "skipped";
  note?: string;
}) {
  const dot =
    status === "ok"
      ? "bg-wcm-accent"
      : status === "fail"
        ? "bg-wcm-danger"
        : "bg-wcm-detail";
  const text =
    status === "ok"
      ? "ok"
      : status === "fail"
        ? "fail"
        : "no configurado";
  return (
    <li className="flex items-center justify-between gap-2 text-wcm-text">
      <span className="flex items-center gap-2">
        <span className={cn("h-1.5 w-1.5 rounded-full", dot)} />
        <span>{label}</span>
        {note && (
          <span className="text-[10px] text-muted-foreground">{note}</span>
        )}
      </span>
      <span
        className={cn(
          "text-[10.5px] uppercase tracking-wider",
          status === "ok"
            ? "text-wcm-accent"
            : status === "fail"
              ? "text-wcm-danger"
              : "text-muted-foreground",
        )}
      >
        {text}
      </span>
    </li>
  );
}

function EnvBadge({ env }: { env: string }) {
  const isProd = env === "production" || env === "prod";
  return (
    <span
      className={cn(
        "inline-flex rounded-sm border px-1.5 text-[10px] uppercase tracking-wider",
        isProd
          ? "border-wcm-warning/50 bg-wcm-warning/10 text-wcm-warning"
          : "border-wcm-detail/60 text-wcm-text/80",
      )}
    >
      {env}
    </span>
  );
}

function OverallBadge({ overall }: { overall: "ok" | "degraded" | "fail" }) {
  const map = {
    ok: "border-wcm-accent/50 bg-wcm-accent/10 text-wcm-accent",
    degraded: "border-wcm-warning/50 bg-wcm-warning/10 text-wcm-warning",
    fail: "border-wcm-danger/50 bg-wcm-danger/15 text-wcm-danger",
  } as const;
  return (
    <span
      className={cn(
        "inline-flex rounded-sm border px-1.5 text-[10px] uppercase tracking-wider",
        map[overall],
      )}
    >
      {overall}
    </span>
  );
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}
