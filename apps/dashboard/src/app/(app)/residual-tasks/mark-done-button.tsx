"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { Check } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";

export function MarkDoneButton({ taskId }: { taskId: number }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function handleClick() {
    startTransition(async () => {
      try {
        await api.patch(`/api/v1/residual-tasks/${taskId}/status`, {
          status: "done",
        });
        toast.success("Tarea cerrada — sync con ClickUp encolada");
        router.refresh();
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Error inesperado");
      }
    });
  }

  return (
    <Button
      size="sm"
      variant="secondary"
      onClick={handleClick}
      disabled={pending}
    >
      <Check className="h-3 w-3" />
      {pending ? "..." : "Done"}
    </Button>
  );
}
