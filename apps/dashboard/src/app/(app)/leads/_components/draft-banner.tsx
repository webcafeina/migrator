"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { OutreachSequenceRead } from "@/types/api";

interface DraftBannerProps {
  leadId: number;
  className?: string;
}

/**
 * Banner reactivo del estado del contacto comercial del lead. Fetcha
 * la secuencia más reciente del lead y renderiza copy/color/CTA según
 * su `status`:
 *
 * - DRAFT_PENDING_REVIEW + legal_passed → ámbar "Borrador preparado".
 * - DRAFT_PENDING_REVIEW + !legal_passed → rojo "NO aprobable".
 * - READY → lima "Listo para enviar".
 * - IN_PROGRESS → lima animado "Enviando".
 * - PAUSED → ámbar "Pausado".
 * - COMPLETED → gris "Completado".
 * - CANCELLED / OPTED_OUT / sin sequence → no se renderiza.
 *
 * Polling cada 4s mientras hay sequence activa para sincronizar con
 * cambios del `ContactSequencePanel` (que tiene su propio state local
 * y no notifica al banner directamente).
 *
 * Diseño v0.13.3: antes el banner estaba acoplado a `lead.status`
 * (solo se mostraba en OUTREACH_PREPARED) y el copy era estático. Tras
 * el feedback del operador, debe reflejar fielmente el estado de la
 * sequence — un draft aprobado ya no debería mostrar "Borrador
 * preparado" sino "Listo para enviar".
 */
export function DraftBanner({ leadId, className }: DraftBannerProps) {
  const [seq, setSeq] = useState<OutreachSequenceRead | null>(null);

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const list = await api.get<OutreachSequenceRead[]>(
          "/api/v1/outreach/sequences",
          { searchParams: { lead_id: leadId, limit: 5 } },
        );
        // Tomamos la más reciente (el API ya ordena desc por created_at).
        if (alive) setSeq(list[0] ?? null);
      } catch {
        if (alive) setSeq(null);
      }
    }
    void load();
    // Polling 4s — mismo periodo que ContactSequencePanel para
    // sincronización rápida sin saturar. Cuando el operador hace
    // Aprobar/Enviar en el panel, el banner se actualiza en ≤4s.
    const id = setInterval(load, 4000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [leadId]);

  if (!seq) return null;
  const spec = bannerSpec(seq);
  if (!spec) return null;

  return (
    <div
      className={cn(
        "flex items-center gap-3 border-b px-7 py-3 text-xs",
        spec.borderBg,
        className,
      )}
      role="status"
      aria-label={spec.ariaLabel}
    >
      <span
        aria-hidden
        className={cn(
          "h-1.5 w-1.5 shrink-0 rounded-full",
          spec.dotColor,
          spec.animatePulse && "animate-pulse",
        )}
      />
      <div className="flex-1">
        <strong className={cn("font-semibold", spec.titleColor)}>
          {spec.title}
        </strong>
        <span className="ml-2 text-wcm-text/70">{spec.subtitle}</span>
      </div>
      <a
        href="#outreach"
        className={cn(
          "rounded-sm border px-2.5 py-1 text-[11px] font-semibold transition-colors",
          spec.ctaClasses,
        )}
      >
        {spec.cta}
      </a>
    </div>
  );
}

interface BannerSpec {
  borderBg: string;
  dotColor: string;
  titleColor: string;
  title: string;
  subtitle: string;
  cta: string;
  ctaClasses: string;
  ariaLabel: string;
  animatePulse?: boolean;
}

function bannerSpec(seq: OutreachSequenceRead): BannerSpec | null {
  const status = String(seq.status).toUpperCase();
  const legalOk = seq.legal_validation_passed;

  if (status === "CANCELLED" || status === "OPTED_OUT") return null;

  if (status === "DRAFT_PENDING_REVIEW") {
    if (!legalOk) {
      return {
        borderBg: "border-wcm-danger/40 bg-wcm-danger/[0.08]",
        dotColor: "bg-wcm-danger shadow-[0_0_0_2px_rgba(248,113,113,0.18)]",
        titleColor: "text-wcm-danger",
        title: "Borrador NO aprobable",
        subtitle:
          "Validación legal falla — edita el paso afectado y restaura firma + opt-out.",
        cta: "Editar →",
        ctaClasses:
          "border-wcm-danger/50 text-wcm-danger hover:bg-wcm-danger/10",
        ariaLabel: "Borrador de contacto NO aprobable",
      };
    }
    return {
      borderBg: "border-wcm-warning/30 bg-wcm-warning/[0.08]",
      dotColor: "bg-wcm-warning shadow-[0_0_0_2px_rgba(255,171,0,0.18)]",
      titleColor: "text-wcm-warning",
      title: "Borrador de contacto preparado",
      subtitle: "Pendiente de revisión humana antes de enviar.",
      cta: "Revisar →",
      ctaClasses:
        "border-wcm-warning/50 text-wcm-warning hover:bg-wcm-warning/10",
      ariaLabel: "Borrador de contacto pendiente",
    };
  }

  if (status === "READY") {
    return {
      borderBg: "border-wcm-accent/40 bg-wcm-accent/[0.06]",
      dotColor: "bg-wcm-accent shadow-[0_0_0_2px_rgba(177,241,0,0.18)]",
      titleColor: "text-wcm-accent",
      title: "Correos listos para enviar",
      subtitle:
        "Secuencia aprobada. Pulsa Enviar cuando quieras lanzar el primer paso.",
      cta: "Enviar →",
      ctaClasses:
        "border-wcm-accent/50 text-wcm-accent hover:bg-wcm-accent/10",
      ariaLabel: "Secuencia de contacto lista para enviar",
    };
  }

  if (status === "IN_PROGRESS") {
    return {
      borderBg: "border-wcm-accent/40 bg-wcm-accent/[0.06]",
      dotColor: "bg-wcm-accent shadow-[0_0_0_2px_rgba(177,241,0,0.18)]",
      titleColor: "text-wcm-accent",
      title: "Enviando contacto",
      subtitle: "El pipeline está enviando los pasos de la secuencia.",
      cta: "Ver progreso →",
      ctaClasses:
        "border-wcm-accent/50 text-wcm-accent hover:bg-wcm-accent/10",
      ariaLabel: "Contacto en envío",
      animatePulse: true,
    };
  }

  if (status === "PAUSED") {
    return {
      borderBg: "border-wcm-warning/30 bg-wcm-warning/[0.06]",
      dotColor: "bg-wcm-warning shadow-[0_0_0_2px_rgba(255,171,0,0.18)]",
      titleColor: "text-wcm-warning",
      title: "Contacto pausado",
      subtitle: "Reanudable cuando quieras.",
      cta: "Reanudar →",
      ctaClasses:
        "border-wcm-warning/50 text-wcm-warning hover:bg-wcm-warning/10",
      ariaLabel: "Contacto pausado",
    };
  }

  if (status === "COMPLETED") {
    return {
      borderBg: "border-wcm-detail/40 bg-wcm-secondary/30",
      dotColor: "bg-wcm-text/40",
      titleColor: "text-wcm-text/80",
      title: "Contacto completado",
      subtitle: "Todos los pasos de la secuencia fueron procesados.",
      cta: "Ver historial →",
      ctaClasses:
        "border-wcm-detail/60 text-wcm-text/80 hover:bg-wcm-secondary",
      ariaLabel: "Contacto completado",
    };
  }

  return null;
}
