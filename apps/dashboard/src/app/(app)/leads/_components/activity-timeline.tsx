import { cn } from "@/lib/utils";

export interface TimelineEvent {
  /** Etiqueta temporal relativa lista para mostrar ("hace 3d", "ahora"). */
  when: string;
  /** Acción principal del evento ("enriquecido", "fingerprint", ...). */
  what: string;
  /** Detalle secundario en gris. Opcional. */
  why?: string | null;
  /** Si true, dot en lima (evento "positivo" o destacado). */
  highlight?: boolean;
}

interface ActivityTimelineProps {
  events: TimelineEvent[];
  className?: string;
}

/**
 * Timeline vertical compacto del histórico del lead. Eventos como dots
 * sobre línea vertical, con `when` a la izquierda en tabular nums, `what`
 * en texto principal y `why` en muted debajo.
 *
 * El dot lima marca eventos positivos (enriquecimiento exitoso, etc.);
 * el outline gris marca eventos neutros (descubrimiento inicial).
 */
export function ActivityTimeline({ events, className }: ActivityTimelineProps) {
  if (events.length === 0) {
    return (
      <section className={cn("px-7 py-5", className)}>
        <h3 className="mb-3 text-[10.5px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
          Actividad
        </h3>
        <p className="text-xs text-muted-foreground">Sin actividad registrada.</p>
      </section>
    );
  }

  return (
    <section className={cn("px-7 py-5 pb-7", className)}>
      <h3 className="mb-3.5 text-[10.5px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
        Actividad
      </h3>
      <ol className="relative pl-4">
        <div className="absolute left-1 top-1.5 bottom-1.5 w-px bg-wcm-detail/50" />
        {events.map((evt, idx) => (
          <li key={idx} className="relative pb-2.5 pt-1.5 text-xs">
            <span
              className={cn(
                "absolute -left-4 top-2.5 h-[9px] w-[9px] rounded-full border bg-wcm-primary",
                evt.highlight
                  ? "border-wcm-accent bg-wcm-accent"
                  : "border-wcm-detail",
              )}
            />
            <div className="flex gap-3.5">
              <span className="w-[70px] shrink-0 text-[11px] tabular-nums text-muted-foreground">
                {evt.when}
              </span>
              <span className="text-wcm-text">{evt.what}</span>
            </div>
            {evt.why && (
              <div className="mt-0.5 pl-[85px] text-[11px] text-wcm-text/70">
                {evt.why}
              </div>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
