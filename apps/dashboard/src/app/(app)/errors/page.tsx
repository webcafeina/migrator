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
import type { ErrorLogRead } from "@/types/api";

export default async function ErrorsPage() {
  const errors = await api
    .get<ErrorLogRead[]>("/api/v1/errors", { searchParams: { limit: 100 } })
    .catch(() => [] as ErrorLogRead[]);

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h1 className="text-lg font-semibold">Errores recientes</h1>
        <span className="text-xs text-wcm-detail uppercase tracking-wider">
          {errors.length} entrada{errors.length === 1 ? "" : "s"}
        </span>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-32">Fecha</TableHead>
            <TableHead className="w-24">Severidad</TableHead>
            <TableHead>Componente</TableHead>
            <TableHead>Mensaje</TableHead>
            <TableHead className="w-16">Proyecto</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {errors.length === 0 ? (
            <TableRow>
              <TableCell colSpan={5} className="py-8 text-center text-wcm-detail">
                Sin errores registrados.
              </TableCell>
            </TableRow>
          ) : (
            errors.map((err) => (
              <TableRow key={err.id}>
                <TableCell className="text-xs text-wcm-detail">
                  {formatDate(err.at)}
                </TableCell>
                <TableCell>
                  <Badge variant={statusVariant(err.severity)}>
                    {err.severity}
                  </Badge>
                </TableCell>
                <TableCell className="text-wcm-detail">{err.component}</TableCell>
                <TableCell>{truncate(err.message, 80)}</TableCell>
                <TableCell className="tabular-nums text-wcm-detail">
                  {err.project_id ?? "—"}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
