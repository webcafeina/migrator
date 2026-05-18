"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";

import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { LeadRead } from "@/types/api";

interface MarkOptOutDialogProps {
  lead: LeadRead;
  open: boolean;
  onClose: () => void;
}

/**
 * Modal "Marcar opt-out" — registra que el lead solicitó NO ser
 * contactado (típicamente por teléfono / WhatsApp / email manual).
 * Llama `POST /api/v1/leads/{id}/consent` con
 * `action="objection_received"`. El lead pasa a MANUAL_REVIEW
 * (no se borra para mantener trazabilidad RGPD).
 *
 * Nota explicativa: el flujo "automatic opt-out vía link en email"
 * usa el endpoint público `/opt-out?token=…` (sin auth). Este dialog
 * es para opt-outs MANUALES — cuando el operador recibe la objeción
 * por un canal alternativo y debe registrarla.
 */
export function MarkOptOutDialog({
  lead,
  open,
  onClose,
}: MarkOptOutDialogProps) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const noteRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (!open) return;
    setNote("");
    setError(null);
    setTimeout(() => noteRef.current?.focus(), 0);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !pending) onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, pending, onClose]);

  if (!open) return null;

  function handleConfirm() {
    setError(null);
    startTransition(async () => {
      try {
        await api.post(`/api/v1/leads/${lead.id}/consent`, {
          action: "objection_received",
          legal_ground: "6.1.f",
          note: note.trim() || null,
        });
        onClose();
        router.refresh();
      } catch (err) {
        setError(
          err instanceof ApiError ? err.message : "Error al marcar opt-out",
        );
      }
    });
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="optout-dialog-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !pending) onClose();
      }}
    >
      <div
        className={cn(
          "w-full max-w-md rounded-sm border border-wcm-warning/50 bg-wcm-primary p-5 text-xs",
        )}
      >
        <h2
          id="optout-dialog-title"
          className="text-sm font-semibold text-wcm-warning"
        >
          Marcar opt-out manual
        </h2>
        <p className="mt-2 text-wcm-text/80">
          Registra que{" "}
          <strong className="text-wcm-text">
            {lead.business_name ?? lead.url}
          </strong>{" "}
          ha solicitado NO ser contactado (típicamente por canal
          alternativo: teléfono, WhatsApp, email manual). El lead
          pasará a estado <code>manual_review</code> y se escribirá
          AuditLog OPT_OUT para trazabilidad RGPD.
        </p>
        <p className="mt-2 text-[10.5px] text-muted-foreground">
          Para opt-outs automáticos (click en el link del email), el
          flujo usa el endpoint público{" "}
          <code>/opt-out?token=…</code> y no requiere esta acción.
        </p>

        <div className="mt-4 space-y-1">
          <label
            htmlFor="optout-note"
            className="block text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground"
          >
            Nota (opcional — contexto del canal de la objeción)
          </label>
          <textarea
            ref={noteRef}
            id="optout-note"
            rows={3}
            placeholder="Llamó al teléfono pidiendo no recibir más emails. Atendido por X."
            value={note}
            onChange={(e) => setNote(e.target.value)}
            disabled={pending}
            maxLength={1000}
            className="w-full resize-y rounded-sm border border-wcm-detail/70 bg-wcm-primary p-2 text-xs text-wcm-text focus:border-wcm-warning focus:outline-none disabled:opacity-50"
          />
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
            type="button"
            onClick={handleConfirm}
            disabled={pending}
            className="rounded-sm border border-wcm-warning bg-wcm-warning/15 px-3 py-1 text-xs font-semibold text-wcm-warning hover:bg-wcm-warning/25 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "Registrando…" : "Confirmar opt-out"}
          </button>
        </div>
      </div>
    </div>
  );
}
