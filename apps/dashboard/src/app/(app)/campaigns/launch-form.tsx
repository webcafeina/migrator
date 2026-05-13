"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api } from "@/lib/api";
import type { EnqueueResponse } from "@/types/api";

export function LaunchCampaignForm() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [sector, setSector] = useState("");
  const [region, setRegion] = useState("");
  const [target, setTarget] = useState(50);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    startTransition(async () => {
      try {
        const res = await api.post<EnqueueResponse>("/api/v1/campaigns/launch", {
          sector,
          region,
          target_count: target,
        });
        toast.success(
          `Campaña encolada · task ${(res.task_id ?? "").slice(0, 8)}…`,
        );
        setSector("");
        setRegion("");
        router.refresh();
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Error inesperado");
      }
    });
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="sector">Sector</Label>
        <Input
          id="sector"
          required
          minLength={2}
          maxLength={120}
          placeholder="restauración, clínica dental, asesoría fiscal..."
          value={sector}
          onChange={(e) => setSector(e.target.value)}
          disabled={pending}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="region">Región</Label>
        <Input
          id="region"
          required
          minLength={2}
          maxLength={120}
          placeholder="Andalucía, Madrid, Extremadura..."
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          disabled={pending}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="target">Objetivo de leads</Label>
        <Input
          id="target"
          type="number"
          min={1}
          max={500}
          value={target}
          onChange={(e) => setTarget(Number(e.target.value))}
          disabled={pending}
        />
      </div>
      <Button type="submit" disabled={pending}>
        {pending ? "Encolando..." : "Lanzar campaña"}
      </Button>
    </form>
  );
}
