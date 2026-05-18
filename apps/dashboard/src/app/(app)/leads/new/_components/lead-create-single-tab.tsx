"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";

import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { LeadRead } from "@/types/api";

interface LeadCreateSingleTabProps {
  sectorSuggestions?: string[];
  regionSuggestions?: string[];
}

/**
 * Form de alta de 1 lead. Mismo patrón que LaunchCampaignForm:
 * useTransition + api.post + toast + router.push.
 *
 * Tras submit exitoso redirige a `/leads?selected=N` para abrir la
 * ficha del lead nuevo en el master-detail. En 409, además del toast
 * de error muestra un botón secundario para abrir el lead existente.
 */
export function LeadCreateSingleTab({
  sectorSuggestions = [],
  regionSuggestions = [],
}: LeadCreateSingleTabProps) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [url, setUrl] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [sector, setSector] = useState("");
  const [region, setRegion] = useState("");
  const [duplicateLeadId, setDuplicateLeadId] = useState<number | null>(null);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setDuplicateLeadId(null);
    startTransition(async () => {
      try {
        const body: Record<string, string> = { url };
        if (businessName) body.business_name = businessName;
        if (sector) body.sector = sector;
        if (region) body.region = region;
        const lead = await api.post<LeadRead>("/api/v1/leads", body);
        toast.success(
          `Lead #${lead.id} creado · fingerprint encolado`,
        );
        router.push(`/leads?selected=${lead.id}`);
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          const existing = (err.details as { existing_lead_id?: number } | null)
            ?.existing_lead_id;
          if (typeof existing === "number") {
            setDuplicateLeadId(existing);
            toast.error(`Esta URL ya existe (lead #${existing})`);
            return;
          }
        }
        toast.error(
          err instanceof ApiError ? err.message : "Error inesperado",
        );
      }
    });
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4 text-xs">
      <Field label="URL" htmlFor="lead-url" required>
        <input
          id="lead-url"
          name="url"
          type="url"
          required
          minLength={4}
          placeholder="https://restauranteejemplo.es"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={pending}
          className={inputClass}
        />
      </Field>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Nombre comercial (opcional)" htmlFor="lead-name">
          <input
            id="lead-name"
            name="business_name"
            maxLength={255}
            placeholder="Restaurante Ejemplo"
            value={businessName}
            onChange={(e) => setBusinessName(e.target.value)}
            disabled={pending}
            className={inputClass}
          />
        </Field>
        <Field label="Sector" htmlFor="lead-sector">
          <input
            id="lead-sector"
            name="sector"
            list="lead-sector-suggestions"
            maxLength={120}
            placeholder="restauración, clínica dental, asesoría fiscal…"
            value={sector}
            onChange={(e) => setSector(e.target.value)}
            disabled={pending}
            className={inputClass}
          />
          {sectorSuggestions.length > 0 && (
            <datalist id="lead-sector-suggestions">
              {sectorSuggestions.map((s) => (
                <option key={s} value={s} />
              ))}
            </datalist>
          )}
        </Field>
        <Field label="Región" htmlFor="lead-region">
          <input
            id="lead-region"
            name="region"
            list="lead-region-suggestions"
            maxLength={120}
            placeholder="Madrid, Andalucía, Extremadura…"
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            disabled={pending}
            className={inputClass}
          />
          {regionSuggestions.length > 0 && (
            <datalist id="lead-region-suggestions">
              {regionSuggestions.map((r) => (
                <option key={r} value={r} />
              ))}
            </datalist>
          )}
        </Field>
      </div>

      <div className="flex flex-wrap items-center gap-3 pt-2">
        <button
          type="submit"
          disabled={pending || !url}
          className="h-8 rounded-sm bg-wcm-accent px-3 text-xs font-semibold text-wcm-primary transition-colors hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {pending ? "Creando…" : "Crear lead →"}
        </button>
        {duplicateLeadId !== null && (
          <Link
            href={`/leads?selected=${duplicateLeadId}`}
            className="text-[11px] text-wcm-text/80 underline-offset-2 hover:text-wcm-accent hover:underline"
          >
            Abrir lead existente #{duplicateLeadId} →
          </Link>
        )}
      </div>
    </form>
  );
}

const inputClass =
  "h-8 w-full rounded-sm border border-wcm-detail/70 bg-wcm-primary px-2 text-xs text-wcm-text placeholder:text-muted-foreground focus:border-wcm-accent focus:outline-none disabled:opacity-50";

function Field({
  label,
  htmlFor,
  required,
  children,
}: {
  label: string;
  htmlFor: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("flex flex-col gap-1")}>
      <label
        htmlFor={htmlFor}
        className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground"
      >
        {label}
        {required && <span className="ml-1 text-wcm-accent">*</span>}
      </label>
      {children}
    </div>
  );
}
