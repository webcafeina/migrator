"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";

import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { LeadRead, ProjectRead } from "@/types/api";

interface ConvertToProjectDialogProps {
  lead: LeadRead;
  open: boolean;
  onClose: () => void;
}

/**
 * Modal "Convertir a proyecto" — crea un proyecto de migración a partir
 * de un lead cualificado. Pre-rellena `source_url`, `client_name`,
 * `builder_source` con los datos del lead; el operador completa
 * `target_domain` (obligatorio) y toggla flags has_ecommerce /
 * is_multilang / preserve_paths.
 *
 * Tras crear, redirige a `/projects/{id}` para que el operador pueda
 * arrancar el pipeline (`projects/{id}` ya tiene botón Start).
 */
export function ConvertToProjectDialog({
  lead,
  open,
  onClose,
}: ConvertToProjectDialogProps) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [clientName, setClientName] = useState(
    lead.business_name ?? lead.url.replace(/^https?:\/\//, ""),
  );
  const [targetDomain, setTargetDomain] = useState("");
  const [hasEcommerce, setHasEcommerce] = useState(false);
  const [isMultilang, setIsMultilang] = useState(false);
  const [preservePaths, setPreservePaths] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const firstInput = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!open) return;
    setClientName(lead.business_name ?? lead.url.replace(/^https?:\/\//, ""));
    setTargetDomain("");
    setError(null);
    setTimeout(() => firstInput.current?.focus(), 0);
  }, [open, lead]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !pending) onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, pending, onClose]);

  if (!open) return null;

  const canSubmit = !pending && clientName.trim() !== "";

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setError(null);
    startTransition(async () => {
      try {
        const body: Record<string, unknown> = {
          client_name: clientName.trim(),
          source_url: lead.url,
          lead_id: lead.id,
          has_ecommerce: hasEcommerce,
          is_multilang: isMultilang,
          preserve_paths: preservePaths,
        };
        if (targetDomain.trim()) body.target_domain = targetDomain.trim();
        if (lead.builder_detected && lead.builder_detected !== "unknown") {
          body.builder_source = lead.builder_detected;
        }
        const proj = await api.post<ProjectRead>("/api/v1/projects", body);
        onClose();
        router.push(`/projects/${proj.id}`);
      } catch (err) {
        setError(
          err instanceof ApiError ? err.message : "Error al crear proyecto",
        );
      }
    });
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="convert-dialog-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !pending) onClose();
      }}
    >
      <form
        onSubmit={handleSubmit}
        className={cn(
          "w-full max-w-md rounded-sm border border-wcm-accent/40 bg-wcm-primary p-5 text-xs",
        )}
      >
        <h2
          id="convert-dialog-title"
          className="text-sm font-semibold text-wcm-accent"
        >
          Convertir lead en proyecto
        </h2>
        <p className="mt-2 text-wcm-text/80">
          Crea un proyecto de migración a partir de{" "}
          <strong className="text-wcm-text">
            {lead.business_name ?? lead.url}
          </strong>
          . Tras crear, te llevamos a la ficha del proyecto para arrancar
          el pipeline.
        </p>

        <div className="mt-4 space-y-3">
          <Field htmlFor="conv-client" label="Nombre cliente *">
            <input
              ref={firstInput}
              id="conv-client"
              type="text"
              maxLength={255}
              required
              value={clientName}
              onChange={(e) => setClientName(e.target.value)}
              disabled={pending}
              className={inputClass}
            />
          </Field>

          <Field
            htmlFor="conv-target"
            label="Dominio destino (opcional, ej. barpepe.com)"
          >
            <input
              id="conv-target"
              type="text"
              maxLength={255}
              placeholder={lead.url.replace(/^https?:\/\//, "")}
              value={targetDomain}
              onChange={(e) => setTargetDomain(e.target.value)}
              disabled={pending}
              className={inputClass}
            />
          </Field>

          <div className="flex flex-col gap-1.5 pt-1">
            <Checkbox
              id="conv-ecom"
              checked={hasEcommerce}
              onChange={setHasEcommerce}
              disabled={pending}
              label="Tiene tienda online (e-commerce)"
            />
            <Checkbox
              id="conv-multi"
              checked={isMultilang}
              onChange={setIsMultilang}
              disabled={pending}
              label="Multilang (WPML)"
            />
            <Checkbox
              id="conv-paths"
              checked={preservePaths}
              onChange={setPreservePaths}
              disabled={pending}
              label="Preservar paths (URLs idénticas a origen — recomendado para SEO)"
            />
          </div>
        </div>

        <div className="mt-3 rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-2 text-[11px] text-muted-foreground">
          <div>
            <strong className="text-wcm-text">URL origen:</strong>{" "}
            <code>{lead.url}</code>
          </div>
          {lead.builder_detected && lead.builder_detected !== "unknown" && (
            <div>
              <strong className="text-wcm-text">Builder detectado:</strong>{" "}
              <code>{lead.builder_detected}</code>
            </div>
          )}
        </div>

        {error && (
          <p className="mt-3 text-[11px] text-wcm-danger">{error}</p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={pending}
            className="rounded-sm border border-wcm-detail/60 px-3 py-1 text-xs text-wcm-text/80 hover:border-wcm-detail hover:text-wcm-text disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={!canSubmit}
            className="rounded-sm bg-wcm-accent px-3 py-1 text-xs font-semibold text-wcm-primary hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "Creando proyecto…" : "Crear proyecto →"}
          </button>
        </div>
      </form>
    </div>
  );
}

const inputClass =
  "h-8 w-full rounded-sm border border-wcm-detail/70 bg-wcm-primary px-2 text-xs text-wcm-text placeholder:text-muted-foreground focus:border-wcm-accent focus:outline-none disabled:opacity-50";

function Field({
  htmlFor,
  label,
  children,
}: {
  htmlFor: string;
  label: string;
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

function Checkbox({
  id,
  checked,
  onChange,
  disabled,
  label,
}: {
  id: string;
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <label
      htmlFor={id}
      className="flex items-baseline gap-2 text-xs text-wcm-text/90"
    >
      <input
        id={id}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="h-3.5 w-3.5 cursor-pointer accent-wcm-accent disabled:opacity-50"
      />
      {label}
    </label>
  );
}
