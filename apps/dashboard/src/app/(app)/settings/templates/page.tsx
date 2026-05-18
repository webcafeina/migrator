import Link from "next/link";

import { api } from "@/lib/api";

import { TemplateManager } from "./_components/template-manager";

interface TemplateRead {
  id: number;
  name: string;
  subject_template: string;
  body_template: string;
  language: string;
  body_html_template: string | null;
  cta_label: string | null;
  cta_url: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * `/settings/templates` — CRUD de plantillas Jinja2 usadas por el
 * composer. Lectura abierta a todos; escritura admin only (lo
 * gestiona el backend).
 */
export default async function TemplatesPage() {
  const templates = await api
    .get<TemplateRead[]>("/api/v1/templates")
    .catch(() => [] as TemplateRead[]);

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold text-wcm-text">
            Plantillas de contacto
          </h1>
          <p className="text-xs text-muted-foreground">
            Plantillas Jinja2 que el composer aplica al generar
            borradores de contacto comercial. Las sequences ya
            generadas no se ven afectadas al editar plantillas (se
            guardan como snapshot).
          </p>
        </div>
        <Link
          href="/settings"
          className="text-xs text-wcm-text/70 hover:text-wcm-accent"
        >
          ← Volver a Ajustes
        </Link>
      </header>

      <TemplateManager initialTemplates={templates} />

      <p className="text-[10.5px] text-muted-foreground">
        Solo administradores pueden crear, editar o borrar plantillas
        (afectan a TODOS los drafts futuros). Los operadores pueden
        leer las plantillas para preview.
      </p>
    </div>
  );
}
