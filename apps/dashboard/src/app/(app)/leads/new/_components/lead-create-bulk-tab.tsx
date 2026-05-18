"use client";

import { useRouter } from "next/navigation";
import { useCallback, useState, useTransition } from "react";
import { toast } from "sonner";

import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { LeadBulkCreateResult } from "@/types/api";

import { BulkPreview } from "./bulk-preview";
import type { BulkParseResult } from "./parse-bulk-urls";

interface LeadCreateBulkTabProps {
  sectorSuggestions?: string[];
  regionSuggestions?: string[];
}

/**
 * Tab "Pegar lote": textarea + preview en vivo + metadata aplicada al
 * batch. Submit envía solo las URLs válidas detectadas por el preview.
 *
 * El backend admite máximo 200 — si el preview detecta >200 mostramos
 * mensaje y deshabilitamos submit (mismo límite, evitamos 422 ruidoso).
 */
export function LeadCreateBulkTab({
  sectorSuggestions = [],
  regionSuggestions = [],
}: LeadCreateBulkTabProps) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [raw, setRaw] = useState("");
  const [parsed, setParsed] = useState<BulkParseResult>({
    valid: [],
    invalid: [],
  });
  const [sector, setSector] = useState("");
  const [region, setRegion] = useState("");

  // Estable para que el useMemo del preview no re-corra por identidad.
  const onParsed = useCallback((r: BulkParseResult) => setParsed(r), []);

  const overLimit = parsed.valid.length > 200;
  const canSubmit = !pending && parsed.valid.length > 0 && !overLimit;

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    startTransition(async () => {
      try {
        const body: Record<string, unknown> = { urls: parsed.valid };
        if (sector) body.sector = sector;
        if (region) body.region = region;
        const res = await api.post<LeadBulkCreateResult>(
          "/api/v1/leads/bulk",
          body,
        );
        const { created, skipped_duplicates, failed } = res;
        const summary = `${created.length} creados · ${skipped_duplicates.length} duplicados · ${failed.length} fallos`;
        if (created.length === 0) {
          toast.warning(summary);
        } else {
          toast.success(summary);
        }
        if (failed.length > 0) {
          const reasons = failed
            .slice(0, 3)
            .map((f) => f.reason ?? "desconocido")
            .join(", ");
          toast.warning(`Razones de fallo: ${reasons}`);
        }
        if (created.length > 0) {
          setRaw("");
          router.push("/leads");
        }
      } catch (err) {
        toast.error(
          err instanceof ApiError ? err.message : "Error inesperado",
        );
      }
    });
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4 text-xs">
      <div className="space-y-1">
        <label
          htmlFor="bulk-textarea"
          className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground"
        >
          URLs (1 por línea)
          <span className="ml-1 text-wcm-accent">*</span>
        </label>
        <textarea
          id="bulk-textarea"
          name="urls"
          rows={12}
          placeholder={
            "https://restauranteejemplo.es\n" +
            "clinicaejemplo.com\n" +
            "# Esta línea se ignora (empieza por #)"
          }
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          disabled={pending}
          className={cn(
            "min-h-[200px] w-full resize-y rounded-sm border border-wcm-detail/70 bg-wcm-primary p-2 font-mono text-[11.5px] text-wcm-text placeholder:text-muted-foreground focus:border-wcm-accent focus:outline-none disabled:opacity-50",
          )}
        />
      </div>

      <BulkPreview raw={raw} onParsed={onParsed} />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FieldLite label="Sector (aplicado a todas)" htmlFor="bulk-sector">
          <input
            id="bulk-sector"
            list="bulk-sector-suggestions"
            maxLength={120}
            placeholder="opcional"
            value={sector}
            onChange={(e) => setSector(e.target.value)}
            disabled={pending}
            className={inputClass}
          />
          {sectorSuggestions.length > 0 && (
            <datalist id="bulk-sector-suggestions">
              {sectorSuggestions.map((s) => (
                <option key={s} value={s} />
              ))}
            </datalist>
          )}
        </FieldLite>
        <FieldLite label="Región (aplicada a todas)" htmlFor="bulk-region">
          <input
            id="bulk-region"
            list="bulk-region-suggestions"
            maxLength={120}
            placeholder="opcional"
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            disabled={pending}
            className={inputClass}
          />
          {regionSuggestions.length > 0 && (
            <datalist id="bulk-region-suggestions">
              {regionSuggestions.map((r) => (
                <option key={r} value={r} />
              ))}
            </datalist>
          )}
        </FieldLite>
      </div>

      <button
        type="submit"
        disabled={!canSubmit}
        className="h-8 rounded-sm bg-wcm-accent px-3 text-xs font-semibold text-wcm-primary transition-colors hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {pending
          ? "Procesando lote…"
          : `Enviar lote (${parsed.valid.length}) →`}
      </button>
    </form>
  );
}

const inputClass =
  "h-8 w-full rounded-sm border border-wcm-detail/70 bg-wcm-primary px-2 text-xs text-wcm-text placeholder:text-muted-foreground focus:border-wcm-accent focus:outline-none disabled:opacity-50";

function FieldLite({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={htmlFor}
        className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground"
      >
        {label}
      </label>
      {children}
    </div>
  );
}
