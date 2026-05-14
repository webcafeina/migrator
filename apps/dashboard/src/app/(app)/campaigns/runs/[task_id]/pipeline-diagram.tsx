"use client";

import {
  Check,
  Fingerprint,
  Loader2,
  Search,
  Sparkles,
  XCircle,
} from "lucide-react";

import { cn } from "@/lib/utils";
import type { CampaignRunStatus } from "@/types/api";

type NodeState = "pending" | "active" | "completed" | "failed" | "skipped";

interface NodeProps {
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  title: string;
  subtitle: string;
  state: NodeState;
  caption: string;
}

/**
 * Diagrama horizontal del pipeline de prospección.
 * Calcula los estados de cada nodo desde el snapshot del endpoint
 * GET /api/v1/campaigns/runs/{task_id}.
 */
export function PipelineDiagram({ data }: { data: CampaignRunStatus }) {
  const nodes = computeNodes(data);
  return (
    <section className="space-y-2">
      <h2 className="text-xs uppercase tracking-wider text-wcm-detail">
        Pipeline
      </h2>
      <div className="flex items-stretch gap-2 sm:gap-3 overflow-x-auto pb-2">
        <PipelineNode {...nodes.prospect} />
        <Connector active={nodes.prospect.state === "completed" && nodes.fingerprint.state === "active"} />
        <PipelineNode {...nodes.fingerprint} />
        <Connector active={nodes.fingerprint.state !== "pending" && nodes.enrich.state === "active"} />
        <PipelineNode {...nodes.enrich} />
      </div>
    </section>
  );
}

// ---------- Subcomponents ----------

function PipelineNode({ icon: Icon, title, subtitle, state, caption }: NodeProps) {
  const variant = NODE_VARIANTS[state];
  return (
    <div
      className={cn(
        "flex-1 min-w-[150px] flex flex-col items-center justify-between gap-2 rounded-sm border p-3 text-center transition-colors",
        variant.container,
        state === "active" && "wcm-node-active",
      )}
    >
      <div
        className={cn(
          "flex h-10 w-10 items-center justify-center rounded-full",
          variant.iconWrap,
        )}
      >
        {state === "active" ? (
          <Loader2 className="h-5 w-5 animate-spin text-wcm-accent" strokeWidth={2.5} />
        ) : state === "completed" ? (
          <Check className="h-5 w-5 text-wcm-accent" strokeWidth={3} />
        ) : state === "failed" ? (
          <XCircle className="h-5 w-5 text-wcm-danger" strokeWidth={2.5} />
        ) : (
          <Icon className={cn("h-5 w-5", variant.icon)} strokeWidth={2} />
        )}
      </div>
      <div className="space-y-0.5">
        <div className={cn("text-sm font-medium", variant.title)}>{title}</div>
        <div className="text-[10px] uppercase tracking-wider text-wcm-detail">
          {subtitle}
        </div>
      </div>
      <div
        className={cn(
          "text-xs tabular-nums",
          variant.captionColor,
        )}
      >
        {caption}
      </div>
    </div>
  );
}

function Connector({ active }: { active: boolean }) {
  return (
    <div className="flex items-center self-center" aria-hidden>
      <div
        className={cn(
          "w-6 sm:w-10 h-0.5 rounded relative overflow-hidden",
          active ? "bg-wcm-accent/30" : "bg-wcm-detail/30",
        )}
      >
        {active && (
          <span
            className="absolute inset-y-0 left-0 w-1/3 bg-wcm-accent"
            style={{
              animation: "wcm-flow 1.2s linear infinite",
            }}
          />
        )}
      </div>
      <style jsx>{`
        @keyframes wcm-flow {
          0% {
            transform: translateX(-100%);
          }
          100% {
            transform: translateX(400%);
          }
        }
      `}</style>
    </div>
  );
}

// ---------- Variants ----------

const NODE_VARIANTS: Record<NodeState, {
  container: string;
  iconWrap: string;
  icon: string;
  title: string;
  captionColor: string;
}> = {
  pending: {
    container: "border-wcm-detail/30 bg-wcm-primary/40",
    iconWrap: "bg-wcm-secondary/30",
    icon: "text-wcm-detail",
    title: "text-wcm-detail",
    captionColor: "text-wcm-detail",
  },
  active: {
    container: "border-wcm-accent/60 bg-wcm-accent/10",
    iconWrap: "bg-wcm-accent/15",
    icon: "text-wcm-accent",
    title: "text-wcm-text",
    captionColor: "text-wcm-accent",
  },
  completed: {
    container: "border-wcm-accent/40 bg-wcm-accent/5",
    iconWrap: "bg-wcm-accent/15",
    icon: "text-wcm-accent",
    title: "text-wcm-text",
    captionColor: "text-wcm-accent",
  },
  failed: {
    container: "border-wcm-danger/40 bg-wcm-danger/10",
    iconWrap: "bg-wcm-danger/15",
    icon: "text-wcm-danger",
    title: "text-wcm-text",
    captionColor: "text-wcm-danger",
  },
  skipped: {
    container: "border-wcm-detail/30 bg-wcm-primary/40 opacity-60",
    iconWrap: "bg-wcm-secondary/30",
    icon: "text-wcm-detail",
    title: "text-wcm-detail",
    captionColor: "text-wcm-detail",
  },
};

// ---------- Logic ----------

function computeNodes(data: CampaignRunStatus): {
  prospect: NodeProps;
  fingerprint: NodeProps;
  enrich: NodeProps;
} {
  const prospect = computeProspectNode(data);
  const { fingerprint, enrich } = computePipelineNodes(data, prospect.state);
  return { prospect, fingerprint, enrich };
}

function computeProspectNode(data: CampaignRunStatus): NodeProps {
  const base = {
    icon: Search,
    title: "Descubrimiento",
    subtitle: "Google Places",
  };

  if (data.state === "FAILURE" || (data.state === "SUCCESS" && data.error)) {
    return { ...base, state: "failed", caption: data.error ?? "Error" };
  }

  // Aún corriendo (no tenemos resultados)
  if (data.prospect === null) {
    if (data.state === "PENDING") {
      return { ...base, state: "active", caption: "En cola…" };
    }
    return { ...base, state: "active", caption: "Buscando…" };
  }

  // Prospect terminó: tenemos outputs
  const created = data.prospect.created;
  const discovered = data.prospect.discovered;
  return {
    ...base,
    state: "completed",
    caption: `${created} de ${discovered} válidos`,
  };
}

function computePipelineNodes(
  data: CampaignRunStatus,
  prospectState: NodeState,
): { fingerprint: NodeProps; enrich: NodeProps } {
  const fpBase = {
    icon: Fingerprint,
    title: "Identificación",
    subtitle: "Detectar builder",
  };
  const enBase = {
    icon: Sparkles,
    title: "Enriquecimiento",
    subtitle: "Emails · phones",
  };

  // Prospect aún no terminó → ambos pendientes
  if (prospectState !== "completed" && prospectState !== "failed") {
    return {
      fingerprint: { ...fpBase, state: "pending", caption: "Esperando…" },
      enrich: { ...enBase, state: "pending", caption: "Esperando…" },
    };
  }

  // Prospect terminó pero sin leads → skipped
  const total = data.pipeline?.total ?? 0;
  if (total === 0) {
    return {
      fingerprint: { ...fpBase, state: "skipped", caption: "Sin leads" },
      enrich: { ...enBase, state: "skipped", caption: "Sin leads" },
    };
  }

  const by = data.pipeline?.by_status ?? {};
  const discovered = by.discovered ?? 0;
  const fingerprinted = by.fingerprinted ?? 0;
  const enriched = by.enriched ?? 0;
  const fpDone = fingerprinted + enriched; // ya pasaron por fingerprint
  const fpRemaining = discovered;          // aún sin pasar por fingerprint

  // Fingerprinter
  let fpNode: NodeProps;
  if (fpRemaining === 0 && fpDone === total) {
    fpNode = { ...fpBase, state: "completed", caption: `${fpDone}/${total}` };
  } else if (fpDone > 0 || fpRemaining > 0) {
    fpNode = {
      ...fpBase,
      state: "active",
      caption: `${fpDone}/${total} clasificados`,
    };
  } else {
    fpNode = { ...fpBase, state: "pending", caption: "Esperando…" };
  }

  // Enricher
  let enNode: NodeProps;
  if (enriched === total && total > 0) {
    enNode = { ...enBase, state: "completed", caption: `${enriched}/${total}` };
  } else if (fingerprinted > 0 || enriched > 0) {
    enNode = {
      ...enBase,
      state: "active",
      caption: `${enriched}/${total} enriquecidos`,
    };
  } else {
    enNode = { ...enBase, state: "pending", caption: "Esperando fingerprint" };
  }

  return { fingerprint: fpNode, enrich: enNode };
}
