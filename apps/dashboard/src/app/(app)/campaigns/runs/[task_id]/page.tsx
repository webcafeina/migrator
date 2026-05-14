import Link from "next/link";

import { RunStatus } from "./run-status";

export default async function CampaignRunPage({
  params,
}: {
  params: Promise<{ task_id: string }>;
}) {
  const { task_id } = await params;
  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-lg font-semibold">Progreso de campaña</h1>
          <p className="text-xs text-wcm-detail font-mono">{task_id}</p>
        </div>
        <Link
          href="/campaigns"
          className="text-xs text-wcm-detail uppercase tracking-wider hover:text-wcm-accent"
        >
          ← Lanzar otra
        </Link>
      </div>
      <RunStatus taskId={task_id} />
    </div>
  );
}
