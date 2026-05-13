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
import { formatDate, truncate } from "@/lib/utils";
import type { ProjectRead } from "@/types/api";

export default async function ProjectsPage() {
  const projects = await api
    .get<ProjectRead[]>("/api/v1/projects")
    .catch(() => [] as ProjectRead[]);

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h1 className="text-lg font-semibold">Proyectos</h1>
        <span className="text-xs text-wcm-detail uppercase tracking-wider">
          {projects.length} proyecto{projects.length === 1 ? "" : "s"}
        </span>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">ID</TableHead>
            <TableHead>Cliente</TableHead>
            <TableHead>Origen</TableHead>
            <TableHead>Destino</TableHead>
            <TableHead>Builder</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="w-32">Iniciado</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {projects.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} className="py-8 text-center text-wcm-detail">
                Sin proyectos todavía.
              </TableCell>
            </TableRow>
          ) : (
            projects.map((p) => (
              <TableRow key={p.id}>
                <TableCell className="tabular-nums text-wcm-detail">
                  {p.id}
                </TableCell>
                <TableCell>
                  <Link
                    href={`/projects/${p.id}`}
                    className="hover:text-wcm-accent"
                  >
                    {p.client_name}
                  </Link>
                </TableCell>
                <TableCell className="text-wcm-detail">
                  {truncate(String(p.source_url), 40)}
                </TableCell>
                <TableCell className="text-wcm-detail">
                  {p.target_domain ?? "—"}
                </TableCell>
                <TableCell>
                  {p.builder_source ? (
                    <Badge variant="default">{p.builder_source}</Badge>
                  ) : (
                    <span className="text-wcm-detail">—</span>
                  )}
                </TableCell>
                <TableCell>
                  <Badge variant={statusVariant(p.status)}>{p.status}</Badge>
                </TableCell>
                <TableCell className="text-xs text-wcm-detail">
                  {formatDate(p.started_at)}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
