import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { ApiError, api } from "@/lib/api";
import type { LeadRead } from "@/types/api";

import { LeadDetailPane } from "../_components/lead-detail-pane";

/**
 * Vista full-page del detalle de un lead. Sirve para:
 * - Deep links: enlaces externos `/leads/19`, compartir, abrir en
 *   nueva pestaña con Cmd+Click desde la lista del master-detail.
 * - Responsive < 1280 px: cuando el `LeadsWorkspace` colapsa a una
 *   sola columna y el usuario navega al detalle, la URL pasa de
 *   `/leads?selected=19` a `/leads/19` (al pulsar `↵` en la lista).
 *
 * Reusa el mismo `LeadDetailPane` que el master-detail — un único
 * componente garantiza coherencia entre ambos modos. Sin sector median
 * ni percentile en esta vista (requeriría un fetch agregado adicional);
 * el ScorePanel omite esas capas silenciosamente y muestra solo cifra
 * + barra.
 */
export default async function LeadDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let lead: LeadRead;
  try {
    lead = await api.get<LeadRead>(`/api/v1/leads/${id}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      notFound();
    }
    throw e;
  }

  return (
    <div className="-m-6 flex h-[calc(100vh-3.5rem)] flex-col">
      <div className="flex shrink-0 items-center gap-3 border-b border-wcm-detail/40 bg-wcm-primary px-4 py-2 text-xs text-muted-foreground">
        <Link
          href="/leads"
          className="inline-flex items-center gap-1 hover:text-wcm-accent"
        >
          <ArrowLeft className="h-3 w-3" /> Lista de leads
        </Link>
        <span aria-hidden>·</span>
        <Link
          href={`/leads?selected=${lead.id}`}
          className="hover:text-wcm-accent"
        >
          Abrir en master-detail
        </Link>
      </div>
      <LeadDetailPane lead={lead} className="flex-1" />
    </div>
  );
}
