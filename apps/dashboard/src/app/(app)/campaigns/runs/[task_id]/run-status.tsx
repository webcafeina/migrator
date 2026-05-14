"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { Badge, statusVariant } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import type { CampaignRunStatus } from "@/types/api";
import { PipelineDiagram } from "./pipeline-diagram";

const POLL_INTERVAL_MS = 2000;
const MAX_DURATION_MS = 15 * 60 * 1000; // 15 min hard cap

interface Props {
  taskId: string;
}

export function RunStatus({ taskId }: Props) {
  const [data, setData] = useState<CampaignRunStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const startedAtRef = useRef<number>(Date.now());
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const next = await api.get<CampaignRunStatus>(
        `/api/v1/campaigns/runs/${taskId}`,
      );
      setData(next);
      setError(null);

      const done = isFinal(next);
      const expired = Date.now() - startedAtRef.current > MAX_DURATION_MS;
      if (!done && !expired) {
        timerRef.current = setTimeout(fetchStatus, POLL_INTERVAL_MS);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Error consultando estado");
      // Reintentar más espaciado tras un error
      timerRef.current = setTimeout(fetchStatus, POLL_INTERVAL_MS * 3);
    }
  }, [taskId]);

  useEffect(() => {
    fetchStatus();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [fetchStatus]);

  if (error && !data) {
    return <p className="text-wcm-danger text-sm">{error}</p>;
  }
  if (!data) {
    return <p className="text-wcm-detail text-sm">Consultando…</p>;
  }

  return (
    <div className="space-y-6">
      <StateBanner data={data} />
      <PipelineDiagram data={data} />
      {data.prospect && <ProspectPanel data={data} />}
      {data.pipeline && data.pipeline.total > 0 && <LeadsList data={data} />}
      {data.prospect?.warnings && data.prospect.warnings.length > 0 && (
        <WarningsList warnings={data.prospect.warnings} />
      )}
    </div>
  );
}

// ---------- subcomponentes ----------

function StateBanner({ data }: { data: CampaignRunStatus }) {
  const map: Record<CampaignRunStatus["state"], { label: string; variant: ReturnType<typeof statusVariant> }> = {
    PENDING: { label: "En cola — esperando worker", variant: "neutral" },
    STARTED: { label: "Ejecutándose…", variant: "default" },
    SUCCESS: { label: "Prospección finalizada", variant: "success" },
    FAILURE: { label: "Falló", variant: "danger" },
    RETRY: { label: "Reintentando…", variant: "warning" },
  };
  const info = map[data.state] ?? { label: data.state, variant: "muted" as const };

  return (
    <div className="flex items-center justify-between border border-wcm-detail/30 bg-wcm-primary/40 p-3 rounded-sm">
      <div className="flex items-center gap-3">
        <Badge variant={info.variant}>{info.label}</Badge>
        {data.prospect?.query && (
          <span className="text-xs text-wcm-detail">
            query: <span className="text-wcm-text">{data.prospect.query}</span>
          </span>
        )}
      </div>
      {data.error && (
        <span className="text-xs text-wcm-danger truncate max-w-md" title={data.error}>
          {data.error}
        </span>
      )}
    </div>
  );
}

function ProspectPanel({ data }: { data: CampaignRunStatus }) {
  const p = data.prospect!;
  return (
    <section className="space-y-2">
      <h2 className="text-xs uppercase tracking-wider text-wcm-detail">
        Descubrimiento (Google Places)
      </h2>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat label="Descubiertos" value={p.discovered} />
        <Stat label="Creados" value={p.created} accent />
        <Stat label="Duplicados" value={p.skipped_duplicate} />
        <Stat label="Sin web" value={p.skipped_no_website} />
      </div>
    </section>
  );
}

function LeadsList({ data }: { data: CampaignRunStatus }) {
  const total = data.pipeline!.total;
  const enriched = data.pipeline!.by_status.enriched ?? 0;
  const pct = total > 0 ? Math.round((enriched / total) * 100) : 0;

  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between">
        <h2 className="text-xs uppercase tracking-wider text-wcm-detail">
          Leads en esta campaña
        </h2>
        <span className="text-xs tabular-nums text-wcm-detail">
          {enriched}/{total} listos ({pct}%)
        </span>
      </div>
      <div className="h-1.5 w-full bg-wcm-primary rounded-sm overflow-hidden">
        <div
          className="h-full bg-wcm-accent transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-16">ID</TableHead>
            <TableHead>Detalle</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.pipeline!.lead_ids.map((id) => (
            <TableRow key={id}>
              <TableCell className="tabular-nums text-wcm-detail">{id}</TableCell>
              <TableCell>
                <Link
                  href={`/leads/${id}`}
                  className="text-wcm-accent hover:underline"
                >
                  Ver lead {id}
                </Link>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  );
}

function WarningsList({ warnings }: { warnings: string[] }) {
  return (
    <section className="space-y-1">
      <h2 className="text-xs uppercase tracking-wider text-wcm-warning">
        Avisos
      </h2>
      <ul className="text-xs space-y-1 list-disc list-inside text-wcm-warning">
        {warnings.map((w, i) => (
          <li key={i}>{w}</li>
        ))}
      </ul>
    </section>
  );
}

function Stat({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: number;
  accent?: boolean;
}) {
  return (
    <div className="border border-wcm-detail/30 bg-wcm-primary/40 p-3 rounded-sm">
      <div className="text-xs uppercase tracking-wider text-wcm-detail">{label}</div>
      <div
        className={`text-2xl tabular-nums font-semibold ${
          accent ? "text-wcm-accent" : "text-wcm-text"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

// ---------- helpers ----------

function isFinal(s: CampaignRunStatus): boolean {
  if (s.state === "FAILURE") return true;
  if (s.state !== "SUCCESS") return false;
  // SUCCESS pero el chain enrich puede seguir corriendo
  if (!s.pipeline || s.pipeline.total === 0) return true;
  const enriched = s.pipeline.by_status.enriched ?? 0;
  return enriched >= s.pipeline.total;
}
