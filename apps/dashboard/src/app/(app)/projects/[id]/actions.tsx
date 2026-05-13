"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { Pause, Play, RotateCw, X } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
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

  const isRunning = status === "running";
  const isBlocked = ["qa_failed", "blocked_human_input"].includes(status);
  const isTerminal = ["completed", "cancelled"].includes(status);

  return (
    <div className="flex gap-2">
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
      {isTerminal && (
        <span className="inline-flex items-center gap-1 text-xs text-wcm-detail">
          <Pause className="h-3 w-3" /> proyecto cerrado
        </span>
      )}
    </div>
  );
}
