"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Pause, Play, RotateCw, Undo2, X } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { EnqueueResponse } from "@/types/api";

export function ProjectActions({
  projectId,
  status,
}: {
  projectId: number;
  status: string;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  // v0.19.0 — confirmación inline para rollback (acción destructiva).
  const [confirmingRollback, setConfirmingRollback] = useState(false);

  async function call(verb: "start" | "resume" | "cancel") {
    startTransition(async () => {
      try {
        const res = await api.post<EnqueueResponse>(
          `/api/v1/projects/${projectId}/${verb}`,
        );
        toast.success(
          verb === "cancel"
            ? "Proyecto cancelado"
            : `Encolado · task ${(res.task_id ?? "").slice(0, 8)}…`,
        );
        router.refresh();
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Error inesperado");
      }
    });
  }

  async function callRollback() {
    startTransition(async () => {
      try {
        const res = await api.post<EnqueueResponse>(
          `/api/v1/projects/${projectId}/rollback`,
          { confirm: true },
        );
        toast.success(
          `Rollback encolado · task ${(res.task_id ?? "").slice(0, 8)}…`,
        );
        setConfirmingRollback(false);
        router.refresh();
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Error inesperado");
      }
    });
  }

  const isRunning = status === "running";
  const isBlocked = ["qa_failed", "blocked_human_input"].includes(status);
  const isTerminal = ["completed", "cancelled", "rolled_back"].includes(status);
  const canRollback = ["qa_failed", "completed", "blocked_human_input"].includes(status);

  return (
    <div className="flex flex-wrap items-center gap-2">
      {!isRunning && !isTerminal && (
        <Button onClick={() => call("start")} disabled={pending} size="sm">
          <Play className="h-3 w-3" />
          Start
        </Button>
      )}
      {isBlocked && (
        <Button
          onClick={() => call("resume")}
          disabled={pending}
          size="sm"
          variant="secondary"
        >
          <RotateCw className="h-3 w-3" />
          Resume
        </Button>
      )}
      {isRunning && (
        <Button
          onClick={() => call("cancel")}
          disabled={pending}
          size="sm"
          variant="destructive"
        >
          <X className="h-3 w-3" />
          Cancel
        </Button>
      )}
      {canRollback && !confirmingRollback && (
        <Button
          onClick={() => setConfirmingRollback(true)}
          disabled={pending}
          size="sm"
          variant="secondary"
          title="Borra las páginas WP creadas por el deploy. NO restaura cambios previos."
        >
          <Undo2 className="h-3 w-3" />
          Rollback
        </Button>
      )}
      {confirmingRollback && (
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-sm border border-wcm-danger/50 bg-wcm-danger/10 px-2 py-1 text-[11px] text-wcm-danger",
          )}
        >
          <Undo2 className="h-3 w-3" aria-hidden />
          ¿Borrar las páginas WP?
          <button
            type="button"
            onClick={callRollback}
            disabled={pending}
            className="ml-1 rounded-sm bg-wcm-danger px-2 py-0.5 text-[10.5px] font-semibold text-wcm-primary hover:brightness-110 disabled:opacity-50"
          >
            {pending ? "Encolando…" : "Sí, deshacer"}
          </button>
          <button
            type="button"
            onClick={() => setConfirmingRollback(false)}
            disabled={pending}
            className="rounded-sm border border-wcm-detail/60 px-2 py-0.5 text-[10.5px] text-wcm-text/80 hover:border-wcm-detail hover:text-wcm-text"
          >
            Cancelar
          </button>
        </span>
      )}
      {isTerminal && !confirmingRollback && (
        <span className="inline-flex items-center gap-1 text-xs text-wcm-detail">
          <Pause className="h-3 w-3" />{" "}
          {status === "rolled_back"
            ? "proyecto revertido"
            : "proyecto cerrado"}
        </span>
      )}
    </div>
  );
}
