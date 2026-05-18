"use client";

import { useEffect, useState } from "react";
import { Loader2, Target } from "lucide-react";

import { api } from "@/lib/api";
import { cn, formatRelativeTime } from "@/lib/utils";

interface ActiveCampaign {
  id: number;
  task_id: string;
  sector: string;
  region: string;
  target_count: number;
  status: string;
  started_at: string | null;
  lead_count: number;
}

const POLL_INTERVAL_MS = 5000;

interface CampaignProgressCardProps {
  className?: string;
}

/**
 * Card visible solo cuando hay 1+ campañas activas (queued/running).
 *
 * Polea `/api/v1/campaigns/active` cada 5s — mismo endpoint que el
 * indicador del header, pero aquí mostramos detalle completo: barra
 * de progreso `lead_count / target_count`, sector·región, tiempo
 * elapsed, status.
 *
 * Cuando la lista pasa a 0 (todas terminadas), se oculta automáticamente
 * y la página padre puede usar `router.refresh()` para recargar el
 * histórico (la campaña recién terminada aparece como fila nueva).
 */
export function CampaignProgressCard({ className }: CampaignProgressCardProps) {
  const [active, setActive] = useState<ActiveCampaign[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function tick() {
      try {
        const data = await api.get<ActiveCampaign[]>(
          "/api/v1/campaigns/active",
        );
        if (!cancelled) setActive(data);
      } catch {
        // Silencioso — un fallo de poll no debe romper la UI.
      }
      if (!cancelled) {
        timer = setTimeout(tick, POLL_INTERVAL_MS);
      }
    }

    timer = setTimeout(tick, 0);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  if (active === null || active.length === 0) return null;

  return (
    <section
      className={cn(
        "rounded-sm border border-wcm-accent/40 bg-wcm-accent/[0.04] p-5",
        className,
      )}
      aria-live="polite"
    >
      <header className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-wcm-accent">
        <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2.5} aria-hidden />
        {`${active.length} ${active.length === 1 ? "campaña" : "campañas"} en curso`}
      </header>
      <ul className="flex flex-col gap-3">
        {active.map((c) => (
          <ProgressItem key={c.id} campaign={c} />
        ))}
      </ul>
    </section>
  );
}

function ProgressItem({ campaign }: { campaign: ActiveCampaign }) {
  const pct =
    campaign.target_count > 0
      ? Math.min(100, (campaign.lead_count / campaign.target_count) * 100)
      : 0;

  return (
    <li className="flex flex-col gap-2 rounded-sm bg-wcm-primary/40 px-4 py-3">
      <div className="flex flex-wrap items-baseline gap-3 text-xs">
        <Target className="h-3.5 w-3.5 text-wcm-accent" aria-hidden />
        <span className="text-wcm-text">
          <span className="font-medium">{campaign.sector}</span>
          <span className="text-muted-foreground">{` · ${campaign.region}`}</span>
        </span>
        <span className="ml-auto text-[11px] tabular-nums text-muted-foreground">
          {campaign.started_at
            ? `lanzada ${formatRelativeTime(campaign.started_at)}`
            : "encolada"}
        </span>
        <span className="rounded-sm border border-wcm-accent/40 bg-wcm-accent/10 px-1.5 py-0.5 text-[9.5px] font-semibold uppercase tracking-wider text-wcm-accent">
          {campaign.status}
        </span>
      </div>
      <div className="flex items-center gap-3">
        <div className="relative h-1.5 flex-1 overflow-hidden rounded-[1px] bg-wcm-secondary">
          <div
            className="absolute inset-y-0 left-0 bg-wcm-accent transition-[width] duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="w-24 text-right text-[11px] tabular-nums text-wcm-text/80">
          {`${campaign.lead_count} / ${campaign.target_count}`}
        </span>
      </div>
    </li>
  );
}
