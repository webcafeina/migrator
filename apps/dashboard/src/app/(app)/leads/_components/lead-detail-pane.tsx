import { cn, formatRelativeTime } from "@/lib/utils";
import type { LeadRead } from "@/types/api";

import { ActivityTimeline, type TimelineEvent } from "./activity-timeline";
import { EvidenceTable, type EvidenceItem } from "./evidence-table";
import { FingerprintList, type FingerprintItem } from "./fingerprint-list";
import { ScorePanel } from "./score-panel";

interface LeadDetailPaneProps {
  lead: LeadRead;
  /** Mediana de score del sector del lead (de /leads/stats agregado o por sector). */
  sectorMedian?: number | null;
  /** Percentil del lead en el pipeline (0..100). */
  percentile?: number | null;
  className?: string;
}

const COUNTRY_LABELS: Record<string, string> = {
  ES: "España",
  PT: "Portugal",
  FR: "Francia",
};

/**
 * Panel detalle del master-detail. Recibe el lead seleccionado completo
 * y lo renderiza con score panel + acciones primarias + 4 secciones
 * (contacto / identificación / fingerprint / estado del flujo) +
 * evidencia colapsable + timeline derivado.
 *
 * Es presentational puro — no hace fetch ni gestiona estado. Las acciones
 * (componer outreach, opt-out, convertir) son links/forms que el bloque 4
 * conectará al backend; aquí van como botones disabled estilísticamente
 * correctos.
 */
export function LeadDetailPane({
  lead,
  sectorMedian,
  percentile,
  className,
}: LeadDetailPaneProps) {
  const url = typeof lead.url === "string" ? lead.url : String(lead.url);
  const display = lead.business_name ?? url.replace(/^https?:\/\//, "");
  const fingerprints = mapFingerprints(lead);
  const evidence = mapEvidence(lead);
  const timeline = buildTimeline(lead);

  return (
    <article
      className={cn("overflow-y-auto bg-wcm-primary", className)}
      aria-label="Detalle del lead seleccionado"
    >
      {/* Header */}
      <header className="border-b border-wcm-detail/40 px-7 pt-5 pb-3.5">
        <div className="flex flex-wrap items-baseline gap-3.5">
          <div className="min-w-0 flex-1">
            <div className="text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
              {`Leads · lead #${lead.id}`}
            </div>
            <h2 className="mt-1 text-xl font-bold leading-tight">{display}</h2>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-0.5 inline-block text-xs text-wcm-text/70 hover:text-wcm-accent"
            >
              {`${url.replace(/^https?:\/\//, "")} ↗`}
            </a>
          </div>
          <div className="flex flex-wrap items-center gap-3.5 text-[11px] text-muted-foreground">
            {lead.builder_detected && lead.builder_detected !== "unknown" && (
              <span className="rounded-sm bg-wcm-accent/10 px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wider text-wcm-accent">
                {lead.builder_detected}
              </span>
            )}
            {lead.builder_confidence != null && (
              <span>{`conf ${lead.builder_confidence.toFixed(2)}`}</span>
            )}
            <span>{`último crawl ${formatRelativeTime(lead.last_crawl_at)}`}</span>
          </div>
        </div>
      </header>

      <ScorePanel
        score={lead.score}
        percentile={percentile ?? null}
        sectorMedian={sectorMedian ?? null}
        sectorName={lead.sector ?? null}
      />

      {/* Acciones */}
      <div className="flex gap-2 border-b border-wcm-detail/40 px-7 py-4">
        <Action primary>Componer outreach →</Action>
        <Action>Convertir a proyecto</Action>
        <Action>Re-fingerprint</Action>
        <Action danger>Marcar opt-out</Action>
      </div>

      {/* Secciones 2x2 */}
      <div className="grid grid-cols-2">
        <Section title="Contacto" borderRight>
          <ContactList lead={lead} />
        </Section>

        <Section title="Identificación">
          <DefList
            items={[
              ["empresa", lead.business_name ?? "—"],
              ["sector", lead.sector ?? "—"],
              ["región", lead.region ?? "—"],
              ["país", COUNTRY_LABELS[lead.country ?? "ES"] ?? (lead.country ?? "—")],
              ["descubierto", formatRelativeTime(lead.created_at)],
            ]}
          />
        </Section>

        <Section title="Fingerprint" borderRight>
          {fingerprints.length > 0 ? (
            <FingerprintList items={fingerprints} />
          ) : (
            <p className="text-xs text-muted-foreground">
              Sin fingerprint todavía. Lanza re-fingerprint para clasificar.
            </p>
          )}
        </Section>

        <Section title="Estado del flujo">
          <DefList
            items={[
              ["status", lead.status.replace(/_/g, " ")],
              [
                "embedding",
                lead.embedding_at
                  ? `${lead.embedding_model ?? "—"} · ${formatRelativeTime(lead.embedding_at)}`
                  : "no generado",
              ],
              [
                "creado",
                formatRelativeTime(lead.created_at),
              ],
              [
                "actualizado",
                formatRelativeTime(lead.updated_at),
              ],
            ]}
          />
        </Section>
      </div>

      <EvidenceTable items={evidence} />

      <ActivityTimeline events={timeline} />
    </article>
  );
}

// ---------- Mapeos ----------

/**
 * `builder_evidence` es JSON heterogéneo (cada detección tiene name,
 * category, confidence, evidence). Aquí lo normalizamos a la shape que
 * espera FingerprintList.
 */
function mapFingerprints(lead: LeadRead): FingerprintItem[] {
  const raw = lead.builder_evidence ?? [];
  return raw
    .map((d) => {
      const name = String(d["name"] ?? "");
      const category = String(d["category"] ?? "");
      const confidence = Number(d["confidence"] ?? 0);
      if (!name) return null;
      return { technology: name, category, confidence };
    })
    .filter((x): x is FingerprintItem => x !== null);
}

function mapEvidence(lead: LeadRead): EvidenceItem[] {
  const raw = lead.builder_evidence ?? [];
  return raw
    .map((d) => {
      const name = String(d["name"] ?? "");
      const category = String(d["category"] ?? "");
      const confidence = Number(d["confidence"] ?? 0);
      const ev = d["evidence"];
      const evidence = Array.isArray(ev) ? ev.map(String) : [];
      if (!name) return null;
      return { technology: name, category, confidence, evidence };
    })
    .filter((x): x is EvidenceItem => x !== null);
}

/**
 * Timeline derivado del propio lead (sin AuditLog). Tres eventos
 * canónicos: descubierto (siempre), fingerprint (si hay builder),
 * enriquecido (si hay emails/phones/socials).
 */
function buildTimeline(lead: LeadRead): TimelineEvent[] {
  const events: TimelineEvent[] = [];
  const hasContact =
    lead.emails.length > 0 ||
    lead.phones.length > 0 ||
    Object.keys(lead.social_links).length > 0;

  if (hasContact) {
    events.push({
      when: formatRelativeTime(lead.updated_at),
      what: "enriquecido",
      why: `${lead.emails.length} email(s) · ${lead.phones.length} teléfono(s) · ${Object.keys(lead.social_links).length} red(es)`,
      highlight: true,
    });
  }
  if (lead.builder_detected && lead.builder_detected !== "unknown") {
    events.push({
      when: formatRelativeTime(lead.last_crawl_at ?? lead.updated_at),
      what: "fingerprint",
      why: `${lead.builder_detected} · conf ${lead.builder_confidence?.toFixed(2) ?? "—"}`,
      highlight: true,
    });
  }
  events.push({
    when: formatRelativeTime(lead.created_at),
    what: "descubierto",
    why: `sector ${lead.sector ?? "—"} · región ${lead.region ?? "—"}`,
  });
  return events;
}

// ---------- Subcomponentes UI ----------

function Section({
  title,
  borderRight,
  children,
}: {
  title: string;
  borderRight?: boolean;
  children: React.ReactNode;
}) {
  return (
    <section
      className={cn(
        "border-b border-wcm-detail/40 px-7 py-4",
        borderRight && "border-r",
      )}
    >
      <h3 className="mb-3 text-[10.5px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
        {title}
      </h3>
      {children}
    </section>
  );
}

function DefList({ items }: { items: Array<[string, string]> }) {
  return (
    <dl className="grid grid-cols-[92px_1fr] gap-x-4 gap-y-1 text-xs">
      {items.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted-foreground">{k}</dt>
          <dd className="text-wcm-text">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function ContactList({ lead }: { lead: LeadRead }) {
  if (
    lead.emails.length === 0 &&
    lead.phones.length === 0 &&
    Object.keys(lead.social_links).length === 0
  ) {
    return (
      <p className="text-xs text-muted-foreground">
        Sin contacto. Ejecuta enrich para descubrir emails y teléfonos.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-1">
      {lead.emails.map((email) => (
        <a
          key={email}
          href={`mailto:${email}`}
          className="text-[12.5px] text-wcm-text hover:text-wcm-accent"
        >
          {email}
        </a>
      ))}
      {lead.phones.map((phone) => (
        <a
          key={phone}
          href={`tel:${phone}`}
          className="text-[12.5px] text-wcm-text hover:text-wcm-accent"
        >
          {formatPhoneEs(phone)}
        </a>
      ))}
      {Object.keys(lead.social_links).length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {Object.entries(lead.social_links).map(([net, url]) => (
            <a
              key={net}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-sm border border-wcm-detail/60 px-2 py-0.5 text-[10.5px] text-wcm-text/70 hover:border-wcm-accent/60 hover:text-wcm-accent"
            >
              {net}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

function Action({
  children,
  primary,
  danger,
}: {
  children: React.ReactNode;
  primary?: boolean;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      className={cn(
        "rounded-sm border px-3.5 py-1.5 text-xs transition-colors",
        primary
          ? "border-wcm-accent bg-wcm-accent font-semibold text-wcm-primary hover:brightness-105"
          : danger
            ? "border-wcm-detail/60 text-wcm-danger hover:border-wcm-danger"
            : "border-wcm-detail/60 text-wcm-text hover:border-muted-foreground",
      )}
    >
      {children}
    </button>
  );
}

/**
 * Formatea teléfonos ES como "+34 753 08 67 92". Si no encaja con el
 * patrón ES, lo devuelve tal cual.
 */
function formatPhoneEs(raw: string): string {
  const m = /^\+34(\d{9})$/.exec(raw.replace(/\s+/g, ""));
  if (!m) return raw;
  const d = m[1]!;
  return `+34 ${d.slice(0, 3)} ${d.slice(3, 5)} ${d.slice(5, 7)} ${d.slice(7, 9)}`;
}
