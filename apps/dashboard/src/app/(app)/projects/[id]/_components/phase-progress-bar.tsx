import { cn } from "@/lib/utils";

interface PhaseProgressBarProps {
  total: number;
  completed: number;
  failed: number;
  running: number;
  className?: string;
}

/**
 * Barra horizontal multi-segmento con el progreso global del pipeline
 * de un proyecto. Cada segmento representa un grupo de fases:
 * completadas (lima), fallidas (rojo), en curso (lima con pulse),
 * pendientes (gris).
 *
 * Diseñada para encajar dentro de `ProjectHeader` debajo del nombre
 * del cliente, con la cifra `N/M` a la derecha.
 */
export function PhaseProgressBar({
  total,
  completed,
  failed,
  running,
  className,
}: PhaseProgressBarProps) {
  const safeTotal = Math.max(total, 0);
  if (safeTotal === 0) {
    return (
      <div className={cn("flex items-center gap-3 text-[11px]", className)}>
        <div className="h-1.5 w-full rounded-[1px] bg-wcm-secondary" />
        <span className="shrink-0 tabular-nums text-muted-foreground">
          0/0
        </span>
      </div>
    );
  }
  const pctCompleted = (completed / safeTotal) * 100;
  const pctFailed = (failed / safeTotal) * 100;
  const pctRunning = (running / safeTotal) * 100;

  return (
    <div className={cn("flex items-center gap-3 text-[11px]", className)}>
      <div className="relative h-1.5 w-full overflow-hidden rounded-[1px] bg-wcm-secondary">
        <div
          className="absolute inset-y-0 left-0 bg-wcm-accent"
          style={{ width: `${pctCompleted}%` }}
        />
        <div
          className="absolute inset-y-0 bg-wcm-danger"
          style={{
            left: `${pctCompleted}%`,
            width: `${pctFailed}%`,
          }}
        />
        <div
          className="absolute inset-y-0 animate-pulse bg-wcm-accent/60"
          style={{
            left: `${pctCompleted + pctFailed}%`,
            width: `${pctRunning}%`,
          }}
        />
      </div>
      <span className="shrink-0 tabular-nums text-wcm-text/80">
        {`${completed}/${safeTotal}`}
      </span>
    </div>
  );
}
