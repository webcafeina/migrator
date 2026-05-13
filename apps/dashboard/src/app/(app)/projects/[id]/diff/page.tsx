import Link from "next/link";
import { ArrowLeft, GitCompare, Info } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default async function DiffPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

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
          <GitCompare className="inline h-4 w-4 text-wcm-accent mr-2" />
          Visual diff — Proyecto #{id}
        </h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>
            <Info className="inline h-4 w-4 mr-2" />
            Próximamente
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-wcm-text">
          <p>
            La comparación visual origen vs destino se implementa en{" "}
            <span className="text-wcm-accent">Fase 10</span> (integración con
            R2 + Playwright). Mientras tanto, este endpoint está reservado y la
            estructura del proyecto ya soporta el flujo:
          </p>
          <ol className="list-decimal pl-5 space-y-1 text-wcm-detail">
            <li>
              <code>VisualDiffAgent</code> tomará screenshots de origen y
              destino con Playwright para cada página clave.
            </li>
            <li>
              Aplicará <code>pixelmatch</code> para detectar zonas divergentes
              con threshold configurable (default 0.85).
            </li>
            <li>
              Subirá las 3 imágenes (source/target/overlay) a R2 y persistirá
              el score por página.
            </li>
            <li>
              Esta vista mostrará la galería interactiva con score, zoom y
              navegación entre páginas.
            </li>
          </ol>
        </CardContent>
      </Card>
    </div>
  );
}
