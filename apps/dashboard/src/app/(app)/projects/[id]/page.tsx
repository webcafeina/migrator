import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ClipboardCheck, GitCompare } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, statusVariant } from "@/components/ui/badge";
import { ApiError, api } from "@/lib/api";
import { statusLabel } from "@/lib/labels";
import { formatDate } from "@/lib/utils";
import type { ProjectPhaseRead, ProjectRead } from "@/types/api";
import { ProjectActions } from "./actions";

export default async function ProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let project: ProjectRead;
  try {
    project = await api.get<ProjectRead>(`/api/v1/projects/${id}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      notFound();
    }
    throw e;
  }

  const phases = await api
    .get<ProjectPhaseRead[]>(`/api/v1/projects/${id}/phases`)
    .catch(() => [] as ProjectPhaseRead[]);

  return (
    <div className="space-y-6">
      <Link
        href="/projects"
        className="inline-flex items-center gap-1 text-xs text-wcm-detail hover:text-wcm-accent"
      >
        <ArrowLeft className="h-3 w-3" /> Volver a proyectos
      </Link>

      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold">
            Proyecto #{project.id} — {project.client_name}
          </h1>
          <p className="text-sm text-wcm-detail">{String(project.source_url)}</p>
        </div>
        <ProjectActions projectId={project.id} status={project.status} />
      </div>

      <div className="flex gap-3">
        <Link
          href={`/projects/${id}/checklist`}
          className="inline-flex items-center gap-1.5 rounded-sm border border-wcm-detail bg-wcm-secondary px-3 py-1.5 text-xs hover:border-wcm-accent/50"
        >
          <ClipboardCheck className="h-3 w-3" />
          Checklist humano
        </Link>
        <Link
          href={`/projects/${id}/diff`}
          className="inline-flex items-center gap-1.5 rounded-sm border border-wcm-detail bg-wcm-secondary px-3 py-1.5 text-xs hover:border-wcm-accent/50"
        >
          <GitCompare className="h-3 w-3" />
          Visual diff
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Configuración</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Origen">{String(project.source_url)}</Row>
            <Row label="Destino">{project.target_domain ?? "—"}</Row>
            <Row label="Builder">{project.builder_source ?? "—"}</Row>
            <Row label="E-commerce">
              {project.has_ecommerce ? "sí" : "no"}
            </Row>
            <Row label="Multilang">
              {project.is_multilang
                ? `sí (${(project.langs ?? []).join(", ")})`
                : "no"}
            </Row>
            <Row label="Asset storage">{project.asset_storage}</Row>
            <Row label="Preserve paths">
              {project.preserve_paths ? "sí" : "no"}
            </Row>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Estado</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Status">
              <Badge variant={statusVariant(project.status)}>
                {statusLabel(project.status)}
              </Badge>
            </Row>
            <Row label="Iniciado">{formatDate(project.started_at)}</Row>
            <Row label="Completado">{formatDate(project.completed_at)}</Row>
            <Row label="Go-live estimado">
              {formatDate(project.estimated_go_live_at)}
            </Row>
            <Row label="Visual diff promedio">
              {project.visual_diff_avg_score !== null &&
              project.visual_diff_avg_score !== undefined ? (
                <span className="text-wcm-accent tabular-nums">
                  {project.visual_diff_avg_score.toFixed(2)}
                </span>
              ) : (
                "—"
              )}
            </Row>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Timeline de fases</CardTitle>
        </CardHeader>
        <CardContent>
          {phases.length === 0 ? (
            <p className="text-sm text-wcm-detail">
              Aún sin fases ejecutadas. Pulsa "Start" para arrancar el pipeline.
            </p>
          ) : (
            <ul className="space-y-1">
              {phases.map((ph) => (
                <li
                  key={ph.id}
                  className="flex items-center justify-between border-b border-wcm-detail/30 py-2 text-sm last:border-0"
                >
                  <div className="flex items-center gap-3">
                    <Badge variant={statusVariant(ph.status)}>{statusLabel(ph.status)}</Badge>
                    <span className="font-medium">{ph.phase_name}</span>
                    {ph.attempt > 1 && (
                      <span className="text-xs text-wcm-detail">
                        intento {ph.attempt}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-wcm-detail">
                    {ph.completed_at
                      ? formatDate(ph.completed_at)
                      : ph.started_at
                        ? `iniciada ${formatDate(ph.started_at)}`
                        : ""}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-xs text-wcm-detail uppercase tracking-wider shrink-0">
        {label}
      </span>
      <span className="text-right text-wcm-text break-all">{children}</span>
    </div>
  );
}
