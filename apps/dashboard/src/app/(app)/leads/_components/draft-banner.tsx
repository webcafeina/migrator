import { cn } from "@/lib/utils";

interface DraftBannerProps {
  leadId: number;
  className?: string;
}

/**
 * Banner ámbar visible cuando el lead tiene un borrador de outreach
 * pendiente de revisión humana (status = OUTREACH_PREPARED). Es la
 * forma canónica de avisar al operador: "este lead tiene una secuencia
 * lista — revisa y aprueba/edita antes de enviar".
 *
 * El CTA enlaza a la futura sección de outreach del propio lead (cuando
 * exista) — el anchor `#outreach` queda fijo para no romper la URL.
 */
export function DraftBanner({ leadId, className }: DraftBannerProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-3 border-b border-wcm-warning/30 bg-wcm-warning/[0.08] px-7 py-3 text-xs",
        className,
      )}
      role="status"
      aria-label="Borrador de outreach pendiente"
    >
      <span
        aria-hidden
        className="h-1.5 w-1.5 shrink-0 rounded-full bg-wcm-warning shadow-[0_0_0_2px_rgba(255,171,0,0.18)]"
      />
      <div className="flex-1">
        <strong className="font-semibold text-wcm-warning">
          Borrador outreach preparado
        </strong>
        <span className="ml-2 text-wcm-text/70">
          Pendiente de revisión humana antes de enviar.
        </span>
      </div>
      <a
        href={`/leads/${leadId}#outreach`}
        className="rounded-sm border border-wcm-warning/50 px-2.5 py-1 text-[11px] font-semibold text-wcm-warning hover:bg-wcm-warning/10"
      >
        Revisar →
      </a>
    </div>
  );
}
