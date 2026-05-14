import Link from "next/link";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge, statusVariant } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { statusLabel } from "@/lib/labels";
import { truncate } from "@/lib/utils";
import type { ResidualTaskRead } from "@/types/api";
import { MarkDoneButton } from "./mark-done-button";

export default async function ResidualTasksPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  const params = await searchParams;
  const tasks = await api
    .get<ResidualTaskRead[]>("/api/v1/residual-tasks", {
      searchParams: { status_filter: params.status },
    })
    .catch(() => [] as ResidualTaskRead[]);

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h1 className="text-lg font-semibold">Tareas residuales</h1>
        <span className="text-xs text-wcm-detail uppercase tracking-wider">
          {tasks.length} tarea{tasks.length === 1 ? "" : "s"}
        </span>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">ID</TableHead>
            <TableHead className="w-16">Proyecto</TableHead>
            <TableHead>Categoría</TableHead>
            <TableHead>Título</TableHead>
            <TableHead className="w-24">Asignar</TableHead>
            <TableHead className="w-16 text-right">Min</TableHead>
            <TableHead className="w-28">Status</TableHead>
            <TableHead className="w-24" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {tasks.length === 0 ? (
            <TableRow>
              <TableCell colSpan={8} className="py-8 text-center text-wcm-detail">
                Sin tareas residuales.
              </TableCell>
            </TableRow>
          ) : (
            tasks.map((t) => (
              <TableRow key={t.id}>
                <TableCell className="tabular-nums text-wcm-detail">
                  {t.id}
                </TableCell>
                <TableCell className="tabular-nums">
                  <Link
                    href={`/projects/${t.project_id}/checklist`}
                    className="text-wcm-accent hover:underline"
                  >
                    #{t.project_id}
                  </Link>
                </TableCell>
                <TableCell className="text-xs text-wcm-detail">
                  {t.category}
                </TableCell>
                <TableCell>{truncate(t.title, 60)}</TableCell>
                <TableCell className="text-wcm-detail">
                  {t.assignee_hint ?? "—"}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {t.estimated_minutes ?? "—"}
                </TableCell>
                <TableCell>
                  <Badge variant={statusVariant(t.status)}>{statusLabel(t.status)}</Badge>
                </TableCell>
                <TableCell>
                  {t.status !== "done" && t.status !== "skipped" && (
                    <MarkDoneButton taskId={t.id} />
                  )}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
