import Link from "next/link";
import { ArrowLeft, ClipboardCheck } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, statusVariant } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { statusLabel } from "@/lib/labels";
import { formatDate } from "@/lib/utils";
import type { ResidualTaskRead } from "@/types/api";

export default async function ChecklistPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const tasks = await api
    .get<ResidualTaskRead[]>("/api/v1/residual-tasks", {
      searchParams: { project_id: id },
    })
    .catch(() => [] as ResidualTaskRead[]);

  // Agrupar por categoría
  const byCategory = tasks.reduce<Record<string, ResidualTaskRead[]>>(
    (acc, t) => {
      const cat = t.category;
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(t);
      return acc;
    },
    {},
  );

  const categoriesOrder = [
    "blocking_go_live",
    "client_config",
    "visual_content",
    "post_go_live",
    "other",
  ];

  return (
    <div className="space-y-6">
      <Link
        href={`/projects/${id}`}
        className="inline-flex items-center gap-1 text-xs text-wcm-detail hover:text-wcm-accent"
      >
        <ArrowLeft className="h-3 w-3" /> Volver al proyecto
      </Link>

      <div className="flex items-baseline justify-between">
        <h1 className="text-lg font-semibold">
          <ClipboardCheck className="inline h-4 w-4 text-wcm-accent mr-2" />
          Checklist humano — Proyecto #{id}
        </h1>
        <span className="text-xs text-wcm-detail uppercase tracking-wider">
          {tasks.length} tarea{tasks.length === 1 ? "" : "s"}
        </span>
      </div>

      {tasks.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-wcm-detail">
            Sin tareas residuales registradas para este proyecto.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {categoriesOrder.map((cat) => {
            const items = byCategory[cat];
            if (!items || items.length === 0) return null;
            return (
              <Card key={cat}>
                <CardHeader>
                  <CardTitle>
                    {cat.replace(/_/g, " ")} · {items.length}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {items.map((t) => (
                    <div
                      key={t.id}
                      className="border-l-2 border-wcm-detail pl-3 py-1"
                    >
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="text-sm font-medium">{t.title}</span>
                        <Badge variant={statusVariant(t.status)}>
                          {statusLabel(t.status)}
                        </Badge>
                      </div>
                      <p className="mt-1 text-xs text-wcm-detail whitespace-pre-wrap">
                        {t.description}
                      </p>
                      <div className="mt-1 flex items-center gap-3 text-[10px] text-wcm-detail uppercase tracking-wider">
                        {t.estimated_minutes ? (
                          <span>{t.estimated_minutes} min est.</span>
                        ) : null}
                        {t.assignee_hint ? (
                          <span>asignar: {t.assignee_hint}</span>
                        ) : null}
                        {t.generated_by ? (
                          <span>por {t.generated_by}</span>
                        ) : null}
                        {t.closed_at ? (
                          <span>cerrada {formatDate(t.closed_at)}</span>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
