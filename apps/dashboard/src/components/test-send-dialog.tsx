"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

interface TestSendDialogProps {
  sequenceId: number;
  stepIndex: number;
  open: boolean;
  onClose: () => void;
  /** Email por defecto en el input (operador puede cambiarlo). */
  defaultTo?: string;
}

interface TestSendResponse {
  provider_message_id: string | null;
  to: string;
}

/**
 * Modal "Enviar prueba" — envío real vía Resend a la dirección que el
 * operador tipea. NO crea OutreachSend ni muta status del sequence;
 * solo registra AuditLog `TEST_SEND` para trazabilidad.
 *
 * Validación de email mínima (regex `@` y `.`) antes de pegar al
 * endpoint para evitar 422 obvios. Errores Resend (502) y falta de
 * API key (503) se muestran al operador con su mensaje.
 */
export function TestSendDialog({
  sequenceId,
  stepIndex,
  open,
  onClose,
  defaultTo = "",
}: TestSendDialogProps) {
  const [pending, startTransition] = useTransition();
  const [to, setTo] = useState(defaultTo);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!open) return;
    setTo(defaultTo);
    setError(null);
    setTimeout(() => inputRef.current?.focus(), 0);
  }, [open, defaultTo]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !pending) onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, pending, onClose]);

  if (!open) return null;

  const trimmed = to.trim();
  const looksLikeEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed);

  function handleSend() {
    if (!looksLikeEmail) {
      setError("Email no válido");
      return;
    }
    setError(null);
    startTransition(async () => {
      try {
        const res = await api.post<TestSendResponse>(
          `/api/v1/outreach/sequences/${sequenceId}/steps/${stepIndex}/test-send`,
          { to: trimmed },
        );
        toast.success(`Correo de prueba enviado a ${res.to}`, {
          description: res.provider_message_id
            ? `Resend message id: ${res.provider_message_id}`
            : undefined,
        });
        onClose();
      } catch (err) {
        const msg =
          err instanceof ApiError ? err.message : "Error al enviar prueba";
        setError(msg);
      }
    });
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="test-send-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !pending) onClose();
      }}
    >
      <div
        className={cn(
          "w-full max-w-md rounded-sm border border-wcm-accent/50 bg-wcm-primary p-5 text-xs",
        )}
      >
        <h2
          id="test-send-title"
          className="text-sm font-semibold text-wcm-accent"
        >
          Enviar correo de prueba
        </h2>
        <p className="mt-2 text-wcm-text/80">
          Manda el paso {stepIndex + 1} de esta secuencia a la dirección
          que indiques para verlo en tu bandeja antes de aprobar el envío
          al lead real. Subject prefijado con{" "}
          <code className="text-wcm-text">[PRUEBA]</code> para distinguirlo.
        </p>
        <p className="mt-2 text-[10.5px] text-muted-foreground">
          NO toca el estado de la secuencia. El operador queda registrado
          en el AuditLog como autor del envío de prueba.
        </p>

        <div className="mt-4 space-y-1">
          <label
            htmlFor="test-send-to"
            className="block text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground"
          >
            Destinatario
          </label>
          <input
            ref={inputRef}
            id="test-send-to"
            type="email"
            placeholder="tu-email@webcafeina.com"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && looksLikeEmail && !pending) {
                e.preventDefault();
                handleSend();
              }
            }}
            disabled={pending}
            className="w-full rounded-sm border border-wcm-detail/70 bg-wcm-primary p-2 text-xs text-wcm-text focus:border-wcm-accent focus:outline-none disabled:opacity-50"
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
            onClick={handleSend}
            disabled={pending || !looksLikeEmail}
            className="rounded-sm bg-wcm-accent px-3 py-1 text-xs font-semibold text-wcm-primary hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "Enviando…" : "Enviar prueba"}
          </button>
        </div>
      </div>
    </div>
  );
}
