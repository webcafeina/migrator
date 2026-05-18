"use client";

import { useCallback, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { LeadRead } from "@/types/api";

import { LeadDeleteDialog } from "./lead-delete-dialog";

interface LeadActionsProps {
  lead: LeadRead;
  className?: string;
}

type ActionState =
  | { kind: "idle" }
  | { kind: "loading"; action: ActionId }
  | { kind: "success"; action: ActionId; message: string }
  | { kind: "error"; action: ActionId; message: string };

type ActionId = "compose" | "refingerprint" | "discard";

/**
 * Botones de acción del panel detalle, con feedback inline (loading,
 * success, error). Tras éxito, hace `router.refresh()` para que el lead
 * se vuelva a fetchar y reflejen los cambios de status (p.ej. tras
 * compose el status pasa a OUTREACH_PREPARED y aparece el banner).
 *
 * "Convertir a proyecto" y "Marcar opt-out" quedan disabled hasta que
 * existan endpoints en backend (post-v0.3.0). Disabled con tooltip
 * explicativo, no oculto: el operador ve qué acciones llegan y cuáles
 * faltan.
 */
export function LeadActions({ lead, className }: LeadActionsProps) {
  const router = useRouter();
  const [, startTransition] = useTransition();
  const [state, setState] = useState<ActionState>({ kind: "idle" });
  const [deleteOpen, setDeleteOpen] = useState(false);

  // Validaciones de pre-condición. Se evalúan antes de habilitar cada
  // acción y deciden el `disabledReason` mostrado como tooltip.
  const composeBlock = lead.emails.length === 0 ? "Sin emails: enrich primero" : null;
  const refingerprintBlock = null; // siempre permitido
  const convertBlock = "Implementación en migrador (Fase 7 producto)";
  const isDiscarded = lead.status === "discarded";
  const discardBlock = isDiscarded
    ? "Este lead ya está descartado"
    : null;

  const run = useCallback(
    async (
      actionId: ActionId,
      path: string,
      successMsg: string,
    ): Promise<void> => {
      setState({ kind: "loading", action: actionId });
      try {
        await api.post(path);
        setState({ kind: "success", action: actionId, message: successMsg });
        // Refresh diferido: damos 1.5 s para que el operador vea el mensaje
        // antes de que el Server Component re-fetche el lead.
        setTimeout(() => {
          startTransition(() => router.refresh());
          setState({ kind: "idle" });
        }, 1500);
      } catch (err) {
        const message =
          err instanceof ApiError
            ? err.message
            : "Error inesperado al ejecutar la acción";
        setState({ kind: "error", action: actionId, message });
      }
    },
    [router],
  );

  const inflight = state.kind === "loading";

  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      <ActionButton
        primary
        disabled={inflight}
        disabledReason={composeBlock ?? undefined}
        loading={state.kind === "loading" && state.action === "compose"}
        onClick={() =>
          run(
            "compose",
            `/api/v1/leads/${lead.id}/outreach/compose`,
            "Borrador encolado",
          )
        }
      >
        Componer outreach →
      </ActionButton>

      <ActionButton disabled disabledReason={convertBlock}>
        Convertir a proyecto
      </ActionButton>

      <ActionButton
        disabled={inflight}
        disabledReason={refingerprintBlock ?? undefined}
        loading={state.kind === "loading" && state.action === "refingerprint"}
        onClick={() =>
          run(
            "refingerprint",
            `/api/v1/leads/${lead.id}/refingerprint`,
            "Re-fingerprint encolado",
          )
        }
      >
        Re-fingerprint
      </ActionButton>

      <ActionButton
        warning
        disabled={inflight}
        disabledReason={discardBlock ?? undefined}
        loading={state.kind === "loading" && state.action === "discard"}
        onClick={() =>
          run(
            "discard",
            `/api/v1/leads/${lead.id}/discard`,
            "Lead descartado",
          )
        }
      >
        Descartar
      </ActionButton>

      <ActionButton
        danger
        disabled={inflight}
        onClick={() => setDeleteOpen(true)}
      >
        Borrar definitivo
      </ActionButton>

      {state.kind === "success" && (
        <span className="ml-2 text-xs text-wcm-accent">{`✓ ${state.message}`}</span>
      )}
      {state.kind === "error" && (
        <span className="ml-2 text-xs text-wcm-danger">{state.message}</span>
      )}

      <LeadDeleteDialog
        leadId={lead.id}
        confirmationText={lead.business_name ?? lead.url}
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onDeleted={() => {
          setDeleteOpen(false);
          startTransition(() => router.push("/leads"));
        }}
      />
    </div>
  );
}

function ActionButton({
  children,
  primary,
  warning,
  danger,
  disabled,
  disabledReason,
  loading,
  onClick,
}: {
  children: React.ReactNode;
  primary?: boolean;
  warning?: boolean;
  danger?: boolean;
  disabled?: boolean;
  disabledReason?: string;
  loading?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={disabled ? undefined : onClick}
      disabled={disabled || loading}
      title={disabledReason}
      className={cn(
        "rounded-sm border px-3.5 py-1.5 text-xs transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        primary &&
          "border-wcm-accent bg-wcm-accent font-semibold text-wcm-primary hover:brightness-105",
        warning &&
          !primary &&
          "border-wcm-warning/50 text-wcm-warning hover:border-wcm-warning",
        danger &&
          !primary &&
          !warning &&
          "border-wcm-detail/60 text-wcm-danger hover:border-wcm-danger",
        !primary &&
          !warning &&
          !danger &&
          "border-wcm-detail/60 text-wcm-text hover:border-muted-foreground",
      )}
    >
      {loading ? "…" : children}
    </button>
  );
}
