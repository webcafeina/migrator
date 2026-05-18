"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { EnqueueResponse } from "@/types/api";

interface LaunchCampaignFormProps {
  /** Sugerencias para autocompletado del input sector (datalist). */
  sectorSuggestions?: string[];
  /** Sugerencias para autocompletado del input region (datalist). */
  regionSuggestions?: string[];
  className?: string;
}

/**
 * Form compacto en una línea: sector | región | objetivo | botón. Encaja
 * en la barra superior del rediseño /campaigns y no requiere Card wrapper
 * — el padre decide el chrome (borde, fondo).
 *
 * Tras el submit redirige a `/campaigns/runs/{task_id}` (página existente
 * de detalle vivo) y `router.refresh()` actualiza el histórico de la
 * página de origen cuando se vuelva.
 */
export function LaunchCampaignForm({
  sectorSuggestions = [],
  regionSuggestions = [],
  className,
}: LaunchCampaignFormProps) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [sector, setSector] = useState("");
  const [region, setRegion] = useState("");
  const [target, setTarget] = useState(50);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    startTransition(async () => {
      try {
        const res = await api.post<EnqueueResponse>("/api/v1/campaigns/launch", {
          sector,
          region,
          target_count: target,
        });
        toast.success(
          `Campaña encolada · task ${(res.task_id ?? "").slice(0, 8)}…`,
        );
        setSector("");
        setRegion("");
        if (res.task_id) {
          router.push(`/campaigns/runs/${res.task_id}`);
        } else {
          router.refresh();
        }
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Error inesperado");
      }
    });
  }

  return (
    <form
      onSubmit={onSubmit}
      className={cn(
        "flex flex-wrap items-end gap-3 text-xs",
        className,
      )}
    >
      <Field label="Sector" htmlFor="sector" widthClass="min-w-[200px] flex-1">
        <input
          id="sector"
          name="sector"
          list="sector-suggestions"
          required
          minLength={2}
          maxLength={120}
          placeholder="restauración, clínica dental, asesoría fiscal…"
          value={sector}
          onChange={(e) => setSector(e.target.value)}
          disabled={pending}
          className={inputClass}
        />
        {sectorSuggestions.length > 0 && (
          <datalist id="sector-suggestions">
            {sectorSuggestions.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
        )}
      </Field>

      <Field label="Región" htmlFor="region" widthClass="min-w-[180px] flex-1">
        <input
          id="region"
          name="region"
          list="region-suggestions"
          required
          minLength={2}
          maxLength={120}
          placeholder="Andalucía, Madrid, Extremadura…"
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          disabled={pending}
          className={inputClass}
        />
        {regionSuggestions.length > 0 && (
          <datalist id="region-suggestions">
            {regionSuggestions.map((r) => (
              <option key={r} value={r} />
            ))}
          </datalist>
        )}
      </Field>

      <Field label="Objetivo" htmlFor="target" widthClass="w-24">
        <input
          id="target"
          name="target"
          type="number"
          min={1}
          max={500}
          value={target}
          onChange={(e) => setTarget(Number(e.target.value))}
          disabled={pending}
          className={cn(inputClass, "tabular-nums text-right")}
        />
      </Field>

      <button
        type="submit"
        disabled={pending}
        className="h-8 rounded-sm bg-wcm-accent px-3 text-xs font-semibold text-wcm-primary transition-colors hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {pending ? "Encolando…" : "Lanzar campaña →"}
      </button>
    </form>
  );
}

const inputClass =
  "h-8 w-full rounded-sm border border-wcm-detail/70 bg-wcm-primary px-2 text-xs text-wcm-text placeholder:text-muted-foreground focus:border-wcm-accent focus:outline-none disabled:opacity-50";

function Field({
  label,
  htmlFor,
  widthClass,
  children,
}: {
  label: string;
  htmlFor: string;
  widthClass: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("flex flex-col gap-1", widthClass)}>
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
