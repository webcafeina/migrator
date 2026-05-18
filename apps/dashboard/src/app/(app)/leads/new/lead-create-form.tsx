"use client";

import { useState } from "react";

import { cn } from "@/lib/utils";

import { LeadCreateBulkTab } from "./_components/lead-create-bulk-tab";
import { LeadCreateSingleTab } from "./_components/lead-create-single-tab";

interface LeadCreateFormProps {
  sectorSuggestions?: string[];
  regionSuggestions?: string[];
}

type TabId = "single" | "bulk";

/**
 * Contenedor de pestañas para alta de leads. `useState` (no
 * searchParams) — evita un SSR roundtrip al cambiar de tab y mantiene
 * el formulario rellenado localmente.
 */
export function LeadCreateForm({
  sectorSuggestions = [],
  regionSuggestions = [],
}: LeadCreateFormProps) {
  const [tab, setTab] = useState<TabId>("single");

  return (
    <div className="space-y-4">
      <div
        role="tablist"
        aria-label="Modo de alta"
        className="flex flex-wrap items-center gap-1 border-b border-wcm-detail/40"
      >
        <TabButton id="single" active={tab} onSelect={setTab}>
          Una URL
        </TabButton>
        <TabButton id="bulk" active={tab} onSelect={setTab}>
          Pegar lote
        </TabButton>
      </div>

      <div
        role="tabpanel"
        aria-labelledby={`tab-${tab}`}
        className="pt-2"
      >
        {tab === "single" ? (
          <LeadCreateSingleTab
            sectorSuggestions={sectorSuggestions}
            regionSuggestions={regionSuggestions}
          />
        ) : (
          <LeadCreateBulkTab
            sectorSuggestions={sectorSuggestions}
            regionSuggestions={regionSuggestions}
          />
        )}
      </div>
    </div>
  );
}

function TabButton({
  id,
  active,
  onSelect,
  children,
}: {
  id: TabId;
  active: TabId;
  onSelect: (id: TabId) => void;
  children: React.ReactNode;
}) {
  const isActive = active === id;
  return (
    <button
      type="button"
      id={`tab-${id}`}
      role="tab"
      aria-selected={isActive}
      onClick={() => onSelect(id)}
      className={cn(
        "-mb-px border-b-2 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.08em] transition-colors",
        isActive
          ? "border-wcm-accent text-wcm-accent"
          : "border-transparent text-muted-foreground hover:text-wcm-text",
      )}
    >
      {children}
    </button>
  );
}
