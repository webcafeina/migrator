import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, statusVariant } from "@/components/ui/badge";
import { ApiError, api } from "@/lib/api";
import { statusLabel } from "@/lib/labels";
import { formatDate } from "@/lib/utils";
import type { LeadRead } from "@/types/api";
import { RefingerprintButton } from "./refingerprint-button";

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
    <div className="space-y-6">
      <Link
        href="/leads"
        className="inline-flex items-center gap-1 text-xs text-wcm-detail hover:text-wcm-accent"
      >
        <ArrowLeft className="h-3 w-3" /> Volver a leads
      </Link>

      <div className="flex items-baseline justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold">Lead #{lead.id}</h1>
          <p className="text-sm text-wcm-detail">{String(lead.url)}</p>
        </div>
        <RefingerprintButton leadId={lead.id} />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Identificación</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Empresa">{lead.business_name ?? "—"}</Row>
            <Row label="Sector">{lead.sector ?? "—"}</Row>
            <Row label="Región">{lead.region ?? "—"}</Row>
            <Row label="País">{lead.country}</Row>
            <Row label="Status">
              <Badge variant={statusVariant(lead.status)}>{statusLabel(lead.status)}</Badge>
            </Row>
            <Row label="Score">
              <span className="text-wcm-accent font-semibold tabular-nums">
                {lead.score}
              </span>
            </Row>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Fingerprint</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Builder">
              {lead.builder_detected ? (
                <Badge variant="default">{lead.builder_detected}</Badge>
              ) : (
                "—"
              )}
            </Row>
            <Row label="Confianza">
              <span className="tabular-nums">
                {lead.builder_confidence?.toFixed(3) ?? "—"}
              </span>
            </Row>
            <Row label="Último crawl">{formatDate(lead.last_crawl_at)}</Row>
            <Row label="Embedding">
              {lead.embedding_model ? (
                <span className="text-wcm-detail">
                  {lead.embedding_model} · {formatDate(lead.embedding_at)}
                </span>
              ) : (
                <span className="text-wcm-detail">No generado</span>
              )}
            </Row>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Contacto</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Emails">
              {lead.emails.length === 0
                ? "—"
                : lead.emails.join(", ")}
            </Row>
            <Row label="Teléfonos">
              {lead.phones.length === 0
                ? "—"
                : lead.phones.join(", ")}
            </Row>
            <Row label="Redes">
              {Object.keys(lead.social_links).length === 0
                ? "—"
                : Object.entries(lead.social_links).map(([k, v]) => (
                    <a
                      key={k}
                      href={v}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="mr-2 text-wcm-accent hover:underline"
                    >
                      {k}
                    </a>
                  ))}
            </Row>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Evidencia</CardTitle>
          </CardHeader>
          <CardContent>
            {!lead.builder_evidence || lead.builder_evidence.length === 0 ? (
              <p className="text-sm text-wcm-detail">Sin evidencia capturada</p>
            ) : (
              <pre className="overflow-auto rounded-sm bg-wcm-primary/50 p-3 text-xs text-wcm-text">
                {JSON.stringify(lead.builder_evidence, null, 2)}
              </pre>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-xs text-wcm-detail uppercase tracking-wider shrink-0">
        {label}
      </span>
      <span className="text-right text-wcm-text">{children}</span>
    </div>
  );
}
