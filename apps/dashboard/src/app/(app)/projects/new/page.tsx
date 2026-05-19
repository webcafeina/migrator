import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { ApiError, api } from "@/lib/api";
import type { LeadRead } from "@/types/api";

import { NewProjectWizard } from "./_components/new-project-wizard";

/**
 * `/projects/new` — wizard onboarding de creación de proyecto (v0.18.0).
 *
 * Server Component que opcionalmente fetcha el lead pre-seleccionado
 * (`?lead_id=N`) para pre-rellenar URL/builder/cliente. El resto del
 * trabajo lo hace el Client Component `NewProjectWizard`.
 */
export default async function NewProjectPage({
  searchParams,
}: {
  searchParams: Promise<{ lead_id?: string }>;
}) {
  const { lead_id } = await searchParams;
  let initialLead: LeadRead | null = null;
  if (lead_id) {
    try {
      initialLead = await api.get<LeadRead>(`/api/v1/leads/${lead_id}`);
    } catch (e) {
      // Si el lead no existe / fue borrado, el wizard arranca en blanco.
      if (!(e instanceof ApiError && e.status === 404)) throw e;
    }
  }

  return (
    <div className="space-y-5">
      <header className="space-y-2">
        <Link
          href="/projects"
          className="inline-flex items-center gap-1 self-start text-[11px] text-muted-foreground hover:text-wcm-accent"
        >
          <ArrowLeft className="h-3 w-3" aria-hidden /> Proyectos
        </Link>
        <h1 className="text-xl font-bold leading-tight text-wcm-text">
          Nuevo proyecto de migración
        </h1>
        <p className="text-[11.5px] text-muted-foreground">
          {initialLead
            ? `Pre-rellenado con datos del lead #${initialLead.id}. Puedes editar cualquier campo antes de crear.`
            : "Sigue los 4 pasos para configurar y arrancar la migración. El paso 4 ejecuta los chequeos pre-vuelo y crea el proyecto."}
        </p>
      </header>

      <NewProjectWizard initialLead={initialLead} />
    </div>
  );
}
