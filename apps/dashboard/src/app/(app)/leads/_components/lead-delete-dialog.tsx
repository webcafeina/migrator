"use client";

import { useEffect, useRef, useState, useTransition } from "react";

import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface LeadDeleteDialogProps {
  /** ID del lead a borrar — para construir el path del DELETE. */
  leadId: number;
  /** Texto que el operador debe tipear para confirmar (típicamente
   * `business_name` o `url` del lead). Patrón GitHub. */
  confirmationText: string;
  open: boolean;
  onClose: () => void;
  onDeleted: () => void;
}

/**
 * Dialog modal de confirmación para hard delete de un lead. El
 * operador debe tipear el `confirmationText` (típicamente el nombre
 * comercial del lead) para habilitar el botón rojo "Borrar
 * permanentemente". Patrón inspirado en GitHub (delete repo).
 *
 * Dialog accesible casero con `role="dialog"` + `aria-modal` + focus
 * trap mínimo (no usamos Radix porque no está instalado y la pantalla
 * vive en un solo sitio).
 *
 * El padre (`LeadActions`) controla `open` y se entera del éxito vía
 * `onDeleted` (típicamente redirige a `/leads`).
 */
export function LeadDeleteDialog({
  leadId,
  confirmationText,
  open,
  onClose,
  onDeleted,
}: LeadDeleteDialogProps) {
  const [pending, startTransition] = useTransition();
  const [typed, setTyped] = useState("");
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  // Foco al input al abrir + reset al cerrar.
  useEffect(() => {
    if (open) {
      setTyped("");
      setError(null);
      // Pequeño delay para que el DOM esté listo.
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  // Cerrar con Escape.
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !pending) onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, pending, onClose]);

  if (!open) return null;

  const canConfirm = typed === confirmationText && !pending;

  function handleDelete() {
    if (!canConfirm) return;
    startTransition(async () => {
      try {
        await api.delete(`/api/v1/leads/${leadId}`);
        onDeleted();
      } catch (err) {
        setError(
          err instanceof ApiError ? err.message : "Error al borrar",
        );
      }
    });
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-dialog-title"
      onClick={(e) => {
        // Cerrar al click fuera del modal (solo si no estamos
        // pendientes para evitar cancelar a mitad de petición).
        if (e.target === e.currentTarget && !pending) onClose();
      }}
    >
      <div
        className={cn(
          "w-full max-w-md rounded-sm border border-wcm-danger/40 bg-wcm-primary p-5 text-xs",
        )}
      >
        <h2
          id="delete-dialog-title"
          className="text-sm font-semibold text-wcm-danger"
        >
          Borrar lead permanentemente
        </h2>
        <p className="mt-2 text-wcm-text/80">
          Esta acción NO se puede deshacer. Se borrará la fila del
          lead + sus enriquecimientos + las secuencias de contacto
          asociadas (CASCADE). Si solo quieres ocultarlo del listado,
          usa <strong>Descartar</strong> en su lugar.
        </p>

        <div className="mt-4 space-y-1">
          <label
            htmlFor="confirm-typing"
            className="block text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground"
          >
            Para confirmar, escribe:{" "}
            <code className="text-wcm-text">{confirmationText}</code>
          </label>
          <input
            ref={inputRef}
            id="confirm-typing"
            type="text"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            disabled={pending}
            className="h-8 w-full rounded-sm border border-wcm-detail/70 bg-wcm-primary px-2 text-xs text-wcm-text focus:border-wcm-danger focus:outline-none disabled:opacity-50"
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
            onClick={handleDelete}
            disabled={!canConfirm}
            className="rounded-sm border border-wcm-danger bg-wcm-danger/15 px-3 py-1 text-xs font-semibold text-wcm-danger hover:bg-wcm-danger/25 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "Borrando…" : "Borrar permanentemente"}
          </button>
        </div>
      </div>
    </div>
  );
}
