"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import {
  Globe,
  Pause,
  Play,
  RotateCw,
  Trash2,
  Undo2,
  X,
  Zap,
} from "lucide-react";
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
  // v0.20.0 (ADR-054) — confirmación literal "DELETE PROJECT N".
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleteText, setDeleteText] = useState("");
  // v0.20.0 (ADR-043) — toggle "re-ejecutar todo" para Resume.
  const [forceRerunAll, setForceRerunAll] = useState(false);

  async function call(verb: "start" | "cancel") {
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

  async function callResume() {
    startTransition(async () => {
      try {
        const path = forceRerunAll
          ? `/api/v1/projects/${projectId}/resume?force_rerun_all=true`
          : `/api/v1/projects/${projectId}/resume`;
        const res = await api.post<EnqueueResponse>(path);
        toast.success(
          `${forceRerunAll ? "Resume (re-todo)" : "Resume rápido"} · task ${(res.task_id ?? "").slice(0, 8)}…`,
        );
        router.refresh();
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Error inesperado");
      }
    });
  }

  async function callRestart() {
    startTransition(async () => {
      try {
        const res = await api.post<EnqueueResponse>(
          `/api/v1/projects/${projectId}/restart`,
          { confirm: true },
        );
        toast.success(
          `Re-arranque encolado · task ${(res.task_id ?? "").slice(0, 8)}…`,
        );
        router.refresh();
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Error inesperado");
      }
    });
  }

  async function callPublish() {
    startTransition(async () => {
      try {
        const res = await api.post<EnqueueResponse>(
          `/api/v1/projects/${projectId}/publish`,
        );
        toast.success(
          `Publish encolado · task ${(res.task_id ?? "").slice(0, 8)}…`,
        );
        router.refresh();
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Error inesperado");
      }
    });
  }

  async function callDelete() {
    const expected = `DELETE PROJECT ${projectId}`;
    if (deleteText !== expected) {
      toast.error(`Escribe literalmente "${expected}" para confirmar.`);
      return;
    }
    startTransition(async () => {
      try {
        await api.delete(`/api/v1/projects/${projectId}`, {
          confirm: expected,
        });
        toast.success(`Proyecto ${projectId} eliminado.`);
        setConfirmingDelete(false);
        router.push("/projects");
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
  const canRestart = status === "rolled_back";
  const canPublish = ["completed", "qa_failed"].includes(status);
  // Borrado siempre permitido salvo en running (el endpoint también lo valida).
  const canDelete = !isRunning;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {!isRunning && !isTerminal && (
        <Button onClick={() => call("start")} disabled={pending} size="sm">
          <Play className="h-3 w-3" />
          Start
        </Button>
      )}
      {isBlocked && (
        <span className="inline-flex items-center gap-2">
          <Button
            onClick={callResume}
            disabled={pending}
            size="sm"
            variant="secondary"
          >
            <RotateCw className="h-3 w-3" />
            Resume
          </Button>
          <label className="inline-flex items-center gap-1 text-[11px] text-wcm-text/70">
            <input
              type="checkbox"
              checked={forceRerunAll}
              onChange={(e) => setForceRerunAll(e.target.checked)}
              className="h-3 w-3 accent-wcm-accent"
            />
            re-ejecutar todo desde el principio
          </label>
        </span>
      )}
      {canRestart && (
        <Button
          onClick={callRestart}
          disabled={pending}
          size="sm"
          variant="secondary"
          title="Resetea el proyecto rolled_back y re-arranca el pipeline desde cero."
        >
          <Zap className="h-3 w-3" />
          Re-arrancar
        </Button>
      )}
      {canPublish && (
        <Button
          onClick={callPublish}
          disabled={pending}
          size="sm"
          title="Pasa todas las páginas migradas de draft a publish."
        >
          <Globe className="h-3 w-3" />
          Publicar todo
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
      {canDelete && !confirmingDelete && (
        <Button
          onClick={() => setConfirmingDelete(true)}
          disabled={pending}
          size="sm"
          variant="destructive"
          title="Borrado permanente. Requiere confirmación literal."
        >
          <Trash2 className="h-3 w-3" />
          Eliminar
        </Button>
      )}
      {confirmingDelete && (
        <span
          className={cn(
            "inline-flex flex-wrap items-center gap-1.5 rounded-sm border border-wcm-danger/50 bg-wcm-danger/10 px-2 py-1 text-[11px] text-wcm-danger",
          )}
        >
          <Trash2 className="h-3 w-3" aria-hidden />
          Escribe{" "}
          <code className="rounded-sm bg-wcm-bg-soft px-1 text-[10.5px] text-wcm-text">
            DELETE PROJECT {projectId}
          </code>
          <input
            type="text"
            value={deleteText}
            onChange={(e) => setDeleteText(e.target.value)}
            placeholder={`DELETE PROJECT ${projectId}`}
            className="w-56 rounded-sm border border-wcm-detail bg-wcm-primary px-2 py-0.5 font-mono text-[10.5px] text-wcm-text"
            autoFocus
          />
          <button
            type="button"
            onClick={callDelete}
            disabled={pending || deleteText !== `DELETE PROJECT ${projectId}`}
            className="rounded-sm bg-wcm-danger px-2 py-0.5 text-[10.5px] font-semibold text-wcm-primary hover:brightness-110 disabled:opacity-40"
          >
            {pending ? "Borrando…" : "Eliminar"}
          </button>
          <button
            type="button"
            onClick={() => {
              setConfirmingDelete(false);
              setDeleteText("");
            }}
            disabled={pending}
            className="rounded-sm border border-wcm-detail/60 px-2 py-0.5 text-[10.5px] text-wcm-text/80 hover:border-wcm-detail hover:text-wcm-text"
          >
            Cancelar
          </button>
        </span>
      )}
    </div>
  );
}
