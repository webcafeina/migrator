import { AlertTriangle, CheckCircle2, Circle, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";

interface PreflightCheckData {
  ok: boolean;
  message: string;
  /** Default false si viene undefined (consistente con schema pydantic). */
  blocking?: boolean;
}

interface PreflightDisplayProps {
  loading?: boolean;
  wpTarget?: PreflightCheckData;
  plugins?: Record<string, boolean>;
  source?: PreflightCheckData;
  sourceCredentials?: PreflightCheckData;
  blockingIssues?: string[];
  warnings?: string[];
  className?: string;
}

/**
 * Visualización de los 4 chequeos del preflight (v0.18.0).
 *
 * Cards visuales en grid 2x2 (desktop) o 1col (mobile):
 * - Verde lima si OK.
 * - Rojo danger si fail + blocking.
 * - Ámbar warning si fail + no blocking.
 * - Gris muted en loading o no ejecutado.
 *
 * El wizard usa este componente en el paso 4 para que el operador vea
 * el estado de los 4 chequeos antes de pulsar "Crear y arrancar".
 */
export function PreflightDisplay({
  loading = false,
  wpTarget,
  plugins,
  source,
  sourceCredentials,
  blockingIssues = [],
  warnings = [],
  className,
}: PreflightDisplayProps) {
  return (
    <div className={cn("space-y-3", className)}>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <CheckCard
          label="WP destino"
          sublabel="REST + SSH accesibles"
          check={wpTarget}
          loading={loading}
        />
        <CheckCard
          label="Origen"
          sublabel="URL responde + builder confirmado"
          check={source}
          loading={loading}
        />
        <PluginsCard plugins={plugins} loading={loading} />
        <CheckCard
          label="Credenciales del back"
          sublabel="Wix / Webflow API (opcional)"
          check={sourceCredentials}
          loading={loading}
        />
      </div>

      {(blockingIssues.length > 0 || warnings.length > 0) && (
        <div className="space-y-1.5 rounded-sm border border-wcm-detail/40 bg-wcm-secondary/20 p-3">
          {blockingIssues.length > 0 && (
            <div className="space-y-1">
              <div className="text-[10.5px] font-semibold uppercase tracking-wider text-wcm-danger">
                Bloqueantes ({blockingIssues.length})
              </div>
              <ul className="space-y-0.5 text-[11.5px] text-wcm-text/90">
                {blockingIssues.map((m, i) => (
                  <li key={`b${i}`} className="flex items-start gap-1.5">
                    <XCircle
                      className="mt-0.5 h-3 w-3 shrink-0 text-wcm-danger"
                      aria-hidden
                    />
                    <span>{m}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {warnings.length > 0 && (
            <div className="space-y-1 pt-1">
              <div className="text-[10.5px] font-semibold uppercase tracking-wider text-wcm-warning">
                Avisos ({warnings.length})
              </div>
              <ul className="space-y-0.5 text-[11.5px] text-wcm-text/90">
                {warnings.map((m, i) => (
                  <li key={`w${i}`} className="flex items-start gap-1.5">
                    <AlertTriangle
                      className="mt-0.5 h-3 w-3 shrink-0 text-wcm-warning"
                      aria-hidden
                    />
                    <span>{m}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CheckCard({
  label,
  sublabel,
  check,
  loading,
}: {
  label: string;
  sublabel: string;
  check?: PreflightCheckData;
  loading: boolean;
}) {
  let Icon = Circle;
  let cls = "border-wcm-detail/50 bg-wcm-secondary/30 text-muted-foreground";
  let statusLabel = "pendiente";
  let message = "Sin ejecutar todavía.";

  if (loading) {
    statusLabel = "comprobando…";
  } else if (check) {
    message = check.message;
    if (check.ok) {
      Icon = CheckCircle2;
      cls = "border-wcm-accent/50 bg-wcm-accent/[0.06] text-wcm-accent";
      statusLabel = "OK";
    } else if (check.blocking) {
      Icon = XCircle;
      cls = "border-wcm-danger/50 bg-wcm-danger/[0.06] text-wcm-danger";
      statusLabel = "bloqueante";
    } else {
      Icon = AlertTriangle;
      cls = "border-wcm-warning/50 bg-wcm-warning/[0.06] text-wcm-warning";
      statusLabel = "aviso";
    }
  }

  return (
    <div className={cn("rounded-sm border p-3", cls)}>
      <div className="flex items-start gap-2.5">
        <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        <div className="min-w-0 flex-1 space-y-0.5">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-xs font-semibold">{label}</span>
            <span className="text-[10px] uppercase tracking-wider opacity-80">
              {statusLabel}
            </span>
          </div>
          <div className="text-[10.5px] opacity-80">{sublabel}</div>
          <div className="break-words pt-1 text-[11.5px] text-wcm-text/90">
            {message}
          </div>
        </div>
      </div>
    </div>
  );
}

function PluginsCard({
  plugins,
  loading,
}: {
  plugins?: Record<string, boolean>;
  loading: boolean;
}) {
  const labels: Array<{ key: string; name: string; blocking: boolean }> = [
    // ADR-037 — Bricks es bloqueante (sin él el deploy deja páginas vacías).
    // GF y WC son informativos (el pipeline degrada con ResidualTask).
    { key: "bricks", name: "Bricks Builder", blocking: true },
    { key: "gravity_forms", name: "Gravity Forms", blocking: false },
    { key: "woocommerce", name: "WooCommerce", blocking: false },
  ];
  const present = plugins
    ? labels.filter((l) => plugins[l.key]).length
    : 0;
  const missing = plugins
    ? labels.filter((l) => !plugins[l.key]).length
    : 0;
  const bricksFails = plugins ? plugins.bricks === false : false;

  let cls = "border-wcm-detail/50 bg-wcm-secondary/30 text-muted-foreground";
  if (plugins) {
    if (bricksFails) {
      cls = "border-wcm-danger/50 bg-wcm-danger/[0.06] text-wcm-danger";
    } else if (present === labels.length) {
      cls = "border-wcm-accent/50 bg-wcm-accent/[0.06] text-wcm-accent";
    } else {
      cls = "border-wcm-warning/50 bg-wcm-warning/[0.06] text-wcm-warning";
    }
  }

  return (
    <div className={cn("rounded-sm border p-3", cls)}>
      <div className="space-y-1.5">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-xs font-semibold">Plugins destino</span>
          <span className="text-[10px] uppercase tracking-wider opacity-80">
            {loading
              ? "comprobando…"
              : plugins
                ? `${present}/${labels.length}`
                : "pendiente"}
          </span>
        </div>
        <div className="text-[10.5px] opacity-80">
          Bricks bloqueante · GF/WC informativos (el pipeline degrada)
        </div>
        <ul className="space-y-0.5 pt-1">
          {labels.map((l) => {
            const ok = Boolean(plugins?.[l.key]);
            return (
              <li
                key={l.key}
                className="flex items-baseline gap-1.5 text-[11.5px] text-wcm-text/90"
              >
                <span aria-hidden>{plugins ? (ok ? "✓" : "✗") : "·"}</span>
                <span>{l.name}</span>
                {l.blocking && plugins && !ok && (
                  <span className="text-[9.5px] uppercase tracking-wider">
                    bloqueante
                  </span>
                )}
              </li>
            );
          })}
        </ul>
        {plugins && missing > 0 && !bricksFails && (
          <div className="pt-1 text-[10.5px] opacity-80">
            Los plugins faltantes se documentarán como tareas residuales.
          </div>
        )}
        {plugins && bricksFails && (
          <div className="pt-1 text-[10.5px] opacity-80">
            Instala Bricks Builder antes de arrancar — sin él, las páginas
            se crean vacías.
          </div>
        )}
      </div>
    </div>
  );
}
