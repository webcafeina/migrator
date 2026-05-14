"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Loader2, Target } from "lucide-react";

import { api } from "@/lib/api";

const POLL_INTERVAL_MS = 5000;

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

/**
 * Indicador global en el header. Polea `/api/v1/campaigns/active` cada
 * 5s y muestra una pildora lima si hay 1+ campañas en curso. Multiventana
 * real: lee de BD, no de localStorage.
 */
export function ActiveCampaignsIndicator() {
  const [active, setActive] = useState<ActiveCampaign[]>([]);

  useEffect(() => {
    let cancelled = false;

    async function tick() {
      try {
        const data = await api.get<ActiveCampaign[]>("/api/v1/campaigns/active");
        if (!cancelled) setActive(data);
      } catch {
        // Silencioso — un fallo de poll no debe romper la UI
      }
      if (!cancelled) {
        timer = setTimeout(tick, POLL_INTERVAL_MS);
      }
    }

    let timer: ReturnType<typeof setTimeout> = setTimeout(tick, 0);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []);

  if (active.length === 0) return null;

  const first = active[0];
  const extra = active.length - 1;

  return (
    <Link
      href={`/campaigns/runs/${first.task_id}`}
      className="flex items-center gap-2 rounded-sm border border-wcm-accent/40 bg-wcm-accent/10 px-2.5 py-1 text-xs text-wcm-accent transition-colors hover:border-wcm-accent/60 hover:bg-wcm-accent/15"
      title={
        active.length === 1
          ? `Campaña en curso · ${first.sector} / ${first.region}`
          : `${active.length} campañas en curso`
      }
    >
      <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2.5} />
      <Target className="h-3 w-3" strokeWidth={2.5} />
      <span className="truncate max-w-[160px]">
        {first.sector} · {first.region}
      </span>
      {extra > 0 && (
        <span className="rounded-sm bg-wcm-accent/20 px-1 text-[10px] tabular-nums">
          +{extra}
        </span>
      )}
    </Link>
  );
}
