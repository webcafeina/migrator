import { cn } from "@/lib/utils";

interface QaReport {
  lighthouse_perf_desktop: number | null;
  lighthouse_perf_mobile: number | null;
  lighthouse_a11y_avg: number | null;
  lighthouse_best_practices_avg: number | null;
  lighthouse_seo_avg: number | null;
  html_validator_errors_count: number;
  html_validator_warnings_count: number;
  broken_links_count: number;
  total_links_checked: number;
  https_valid: boolean | null;
  robots_accessible: boolean | null;
  sitemap_accessible: boolean | null;
}

interface QaScorecardsProps {
  report: QaReport;
}

/**
 * Scorecards Lighthouse + counters HTML/links + checks binarios (v0.16.0).
 *
 * Layout grid 4-col en desktop, 2-col mobile. Cada card con label,
 * número grande y color según gravedad (verde >=80 / ámbar 50-79 /
 * rojo <50 para scores; verde 0 / rojo >0 para counters; verde si OK
 * / rojo si fail para booleans).
 */
export function QaScorecards({ report }: QaScorecardsProps) {
  return (
    <div className="space-y-5">
      <section className="space-y-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
          Lighthouse
        </h3>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <ScoreCard
            label="Performance desktop"
            score={report.lighthouse_perf_desktop}
          />
          <ScoreCard
            label="Performance mobile"
            score={report.lighthouse_perf_mobile}
          />
          <ScoreCard label="Accesibilidad" score={report.lighthouse_a11y_avg} />
          <ScoreCard
            label="Best practices"
            score={report.lighthouse_best_practices_avg}
          />
          <ScoreCard label="SEO" score={report.lighthouse_seo_avg} />
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
          HTML W3C
        </h3>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <CountCard
            label="Errores HTML"
            value={report.html_validator_errors_count}
            severityZeroIsGood
          />
          <CountCard
            label="Warnings HTML"
            value={report.html_validator_warnings_count}
            severityZeroIsGood
            warningOnly
          />
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
          Links del destino
        </h3>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <CountCard
            label="Links rotos"
            value={report.broken_links_count}
            severityZeroIsGood
          />
          <CountCard
            label="Total comprobados"
            value={report.total_links_checked}
            neutral
          />
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
          Comprobaciones SEO/SSL
        </h3>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <BoolCard label="HTTPS válido" value={report.https_valid} />
          <BoolCard label="robots.txt accesible" value={report.robots_accessible} />
          <BoolCard
            label="sitemap.xml accesible"
            value={report.sitemap_accessible}
          />
        </div>
      </section>
    </div>
  );
}

function ScoreCard({
  label,
  score,
}: {
  label: string;
  score: number | null;
}) {
  const color =
    score == null
      ? "text-muted-foreground"
      : score >= 80
        ? "text-wcm-accent"
        : score >= 50
          ? "text-wcm-warning"
          : "text-wcm-danger";
  return (
    <div className="rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-3">
      <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
        {label}
      </div>
      <div
        className={cn(
          "mt-1 text-2xl font-bold tabular-nums",
          color,
        )}
      >
        {score != null ? `${score}` : "—"}
        <span className="text-xs font-normal text-muted-foreground">/100</span>
      </div>
    </div>
  );
}

function CountCard({
  label,
  value,
  severityZeroIsGood,
  warningOnly,
  neutral,
}: {
  label: string;
  value: number;
  severityZeroIsGood?: boolean;
  warningOnly?: boolean;
  neutral?: boolean;
}) {
  let color = "text-wcm-text";
  if (neutral) {
    color = "text-wcm-text";
  } else if (severityZeroIsGood) {
    if (value === 0) {
      color = "text-wcm-accent";
    } else if (warningOnly) {
      color = "text-wcm-warning";
    } else {
      color = value > 5 ? "text-wcm-danger" : "text-wcm-warning";
    }
  }
  return (
    <div className="rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-3">
      <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
        {label}
      </div>
      <div className={cn("mt-1 text-2xl font-bold tabular-nums", color)}>
        {value}
      </div>
    </div>
  );
}

function BoolCard({
  label,
  value,
}: {
  label: string;
  value: boolean | null;
}) {
  const cls =
    value === true
      ? "border-wcm-accent/50 bg-wcm-accent/10 text-wcm-accent"
      : value === false
        ? "border-wcm-danger/50 bg-wcm-danger/15 text-wcm-danger"
        : "border-wcm-detail/40 bg-wcm-secondary/30 text-muted-foreground";
  const text = value === true ? "OK" : value === false ? "FAIL" : "—";
  return (
    <div className={cn("rounded-sm border p-3", cls)}>
      <div className="text-[10px] font-semibold uppercase tracking-[0.08em] opacity-80">
        {label}
      </div>
      <div className="mt-1 text-xl font-bold uppercase tracking-wider">
        {text}
      </div>
    </div>
  );
}
