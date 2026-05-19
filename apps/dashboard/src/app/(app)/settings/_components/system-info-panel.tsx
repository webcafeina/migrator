"use client";

import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState, useTransition } from "react";

import { api, ApiError } from "@/lib/api";
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
  /** Datos iniciales fetcheados por el Server Component padre — evita
   *  spinner en el primer render. */
  info: SystemInfoData | null;
}

const POLL_INTERVAL_MS = 30_000;

/**
 * Runtime info del API: version, environment, alembic revision, uptime
 * y resumen de health. v0.15.x:
 *
 * - Polling silencioso cada 30 s para que health/uptime reflejen el
 *   estado actual sin recargar la página.
 * - Botón "Refrescar" para forzar fetch inmediato tras intervenciones
 *   del operador (reinicio de servicio, redeploy).
 * - Dot pulsando junto a "Estado" cuando llega un dato más reciente
 *   (indicador visual sutil de que la info viene del último poll).
 */
export function SystemInfoPanel({ info: initialInfo }: SystemInfoPanelProps) {
  const [info, setInfo] = useState<SystemInfoData | null>(initialInfo);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(
    initialInfo ? new Date() : null,
  );
  const [pulsing, setPulsing] = useState(false);
  const [pending, startTransition] = useTransition();
  const [fetchError, setFetchError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const refresh = useCallback(
    (manual: boolean = false) => {
      if (abortRef.current) abortRef.current.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const exec = async () => {
        try {
          const data = await api.get<SystemInfoData>("/api/v1/system/info", {
            signal: controller.signal,
          });
          setInfo(data);
          setLastUpdated(new Date());
          setFetchError(null);
          // Pulso visual cortito (600 ms) cuando llega data nueva.
          setPulsing(true);
          window.setTimeout(() => setPulsing(false), 600);
        } catch (err) {
          if (err instanceof DOMException && err.name === "AbortError") return;
          setFetchError(
            err instanceof ApiError ? err.message : "Error al refrescar",
          );
        }
      };
      if (manual) startTransition(exec);
      else void exec();
    },
    [],
  );

  // Sincroniza el state interno cuando el prop `initialInfo` cambia
  // (router.refresh() del padre o re-render externo). Sin esto, el
  // componente quedaría stale ante actualizaciones del Server.
  useEffect(() => {
    setInfo(initialInfo);
    if (initialInfo) setLastUpdated(new Date());
  }, [initialInfo]);

  // Polling 30 s. Se cancela al desmontar; cada poll cancela el anterior
  // si aún no resolvió (AbortController).
  useEffect(() => {
    const id = window.setInterval(() => refresh(false), POLL_INTERVAL_MS);
    return () => {
      window.clearInterval(id);
      if (abortRef.current) abortRef.current.abort();
    };
  }, [refresh]);

  if (!info) {
    return (
      <div className="rounded-sm border border-wcm-danger/40 bg-wcm-danger/[0.05] p-4 text-xs text-wcm-text/80">
        <p>
          El API no responde. Comprueba <code>systemctl status webcafeina-api</code>
          {" "}en el servidor.
        </p>
        <button
          type="button"
          onClick={() => refresh(true)}
          disabled={pending}
          className="mt-2 inline-flex items-center gap-1 rounded-sm border border-wcm-detail/60 px-2 py-0.5 text-[10.5px] text-wcm-text hover:border-wcm-accent hover:text-wcm-accent disabled:opacity-50"
        >
          <RefreshCw size={11} className={cn(pending && "animate-spin")} />
          Reintentar
        </button>
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
          <span
            aria-hidden
            className={cn(
              "ml-1 h-1.5 w-1.5 rounded-full bg-wcm-accent transition-opacity duration-500",
              pulsing ? "opacity-100" : "opacity-0",
            )}
            title="Acabo de refrescar"
          />
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

      <div className="flex items-center justify-between gap-2 border-t border-wcm-detail/30 pt-2 text-[10.5px] text-muted-foreground">
        <span>
          {fetchError ? (
            <span className="text-wcm-danger">{fetchError}</span>
          ) : (
            <>actualizado {formatRelativeShort(lastUpdated)}</>
          )}
        </span>
        <button
          type="button"
          onClick={() => refresh(true)}
          disabled={pending}
          aria-label="Refrescar datos del sistema"
          className="inline-flex items-center gap-1 rounded-sm border border-wcm-detail/60 px-2 py-0.5 text-[10.5px] text-wcm-text/80 hover:border-wcm-accent hover:text-wcm-accent disabled:opacity-50"
        >
          <RefreshCw size={11} className={cn(pending && "animate-spin")} />
          {pending ? "Refrescando…" : "Refrescar"}
        </button>
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

function formatRelativeShort(date: Date | null): string {
  if (!date) return "—";
  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (seconds < 5) return "ahora";
  if (seconds < 60) return `hace ${seconds}s`;
  const m = Math.floor(seconds / 60);
  if (m < 60) return `hace ${m}m`;
  const h = Math.floor(m / 60);
  return `hace ${h}h`;
}
