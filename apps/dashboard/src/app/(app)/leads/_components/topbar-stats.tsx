import { cn } from "@/lib/utils";

export interface TopbarStatsData {
  total: number;
  uncontacted: number;
  /** Score medio del pipeline (excluye score=0). null si no hay leads. */
  avgScore: number | null;
  distinctBuilders: number;
}

export interface WorkerHealth {
  status: "ok" | "stale" | "down" | "unknown";
  /** Texto listo para mostrar: "hace 12 min", "hace 3 h", etc. */
  lastSeenLabel?: string | null;
}

interface TopbarStatsProps {
  stats: TopbarStatsData;
  worker?: WorkerHealth;
  className?: string;
}

/**
 * Tira densa de stats agregados para la topbar de /leads. Sustituye al
 * antiguo "MIGRATOR DASHBOARD" redundante.
 *
 * Formato: dato pivote + separador "·" + siguiente dato. Tabular nums
 * para que los números mantengan ancho al cambiar el filtro. Sin iconos:
 * el texto es el dato.
 *
 * Si `avgScore` es null (pipeline recién inicializado), muestra "—" en
 * lugar de "NaN" o "0".
 */
export function TopbarStats({ stats, worker, className }: TopbarStatsProps) {
  const avg = stats.avgScore != null ? Math.round(stats.avgScore) : null;
  return (
    <div
      className={cn(
        "flex items-center gap-[18px] text-[11.5px] text-wcm-text/70",
        className,
      )}
    >
      <Stat value={stats.total} label="leads" />
      <Sep />
      <Stat value={stats.uncontacted} label="sin contactar" />
      <Sep />
      <span>
        score medio{" "}
        <strong className="font-semibold tabular-nums text-wcm-text">
          {avg ?? "—"}
        </strong>
      </span>
      <Sep />
      <Stat value={stats.distinctBuilders} label="builders" />
      {worker && worker.status !== "unknown" && (
        <>
          <span className="mx-1.5 grow" />
          <WorkerHealthDot worker={worker} />
        </>
      )}
    </div>
  );
}

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <span>
      <strong className="font-semibold tabular-nums text-wcm-text">{value}</strong>{" "}
      {label}
    </span>
  );
}

function Sep() {
  return <span className="text-muted-foreground">·</span>;
}

function WorkerHealthDot({ worker }: { worker: WorkerHealth }) {
  const dotColor =
    worker.status === "ok"
      ? "bg-[#5fc591] shadow-[0_0_0_2px_rgba(95,197,145,0.15)]"
      : worker.status === "stale"
        ? "bg-wcm-warning shadow-[0_0_0_2px_rgba(255,171,0,0.15)]"
        : "bg-wcm-danger shadow-[0_0_0_2px_rgba(255,82,82,0.15)]";
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={cn("h-1.5 w-1.5 rounded-full", dotColor)}
        aria-label={`worker ${worker.status}`}
      />
      worker{worker.lastSeenLabel ? ` · ${worker.lastSeenLabel}` : ""}
    </span>
  );
}
