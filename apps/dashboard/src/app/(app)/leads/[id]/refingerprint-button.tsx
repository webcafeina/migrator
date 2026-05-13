"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import type { EnqueueResponse } from "@/types/api";

export function RefingerprintButton({ leadId }: { leadId: number }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function handleClick() {
    startTransition(async () => {
      try {
        const res = await api.post<EnqueueResponse>(
          `/api/v1/leads/${leadId}/refingerprint`,
        );
        toast.success(`Encolado · task ${res.task_id.slice(0, 8)}…`);
        router.refresh();
      } catch (err) {
        toast.error(
          err instanceof ApiError ? err.message : "Error al encolar",
        );
      }
    });
  }

  return (
    <Button variant="secondary" size="sm" onClick={handleClick} disabled={pending}>
      <RefreshCw className="h-3 w-3" />
      {pending ? "Encolando..." : "Re-fingerprint"}
    </Button>
  );
}
