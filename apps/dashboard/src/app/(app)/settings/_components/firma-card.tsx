export interface FirmaData {
  company_legal_name: string;
  company_cif: string | null;
  company_address: string | null;
  company_contact_email: string;
  company_privacy_policy_url: string;
  opt_out_url_base: string;
}

interface FirmaCardProps {
  firma: FirmaData | null;
}

/**
 * Card read-only con los datos legales que el composer aplica al
 * generar borradores de contacto. Coherente con el resto de
 * `/settings`: "el dashboard es solo lectura para configuración —
 * para editar, SSH al servidor". El operador puede ver QUÉ firma se
 * está usando sin tener que SSHear.
 *
 * Si `company_cif` o `company_address` faltan en `.env`, el composer
 * rechaza arrancar (`OutreachComposerError`) — así que en runtime
 * deberían estar siempre. Si vienen null se renderiza warning rojo.
 */
export function FirmaCard({ firma }: FirmaCardProps) {
  if (!firma) {
    return (
      <div className="rounded-sm border border-wcm-danger/40 bg-wcm-danger/[0.05] p-4 text-xs text-wcm-text/80">
        No se pudo recuperar la firma legal. Comprueba que el API
        responde y que las vars <code>COMPANY_*</code> están en
        <code>.env</code>.
      </div>
    );
  }

  const rows: Array<[string, React.ReactNode]> = [
    ["razón social", firma.company_legal_name],
    [
      "cif",
      firma.company_cif ?? (
        <span className="text-wcm-danger">⚠ falta COMPANY_CIF</span>
      ),
    ],
    [
      "dirección",
      firma.company_address ?? (
        <span className="text-wcm-danger">⚠ falta COMPANY_ADDRESS</span>
      ),
    ],
    ["email", firma.company_contact_email],
    [
      "política privacidad",
      <code key="p" className="text-[10.5px]">
        {firma.company_privacy_policy_url}
      </code>,
    ],
    [
      "opt-out base",
      <code key="o" className="text-[10.5px]">
        {firma.opt_out_url_base}
      </code>,
    ],
  ];

  return (
    <div className="space-y-3 rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-4 text-xs">
      <dl className="grid grid-cols-[120px_1fr] gap-x-3 gap-y-2">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-muted-foreground">{k}</dt>
            <dd className="break-all text-wcm-text">{v}</dd>
          </div>
        ))}
      </dl>
      <p className="text-[10.5px] text-muted-foreground">
        Solo lectura. Para editar, SSH al servidor y modifica las
        variables <code>COMPANY_*</code> en{" "}
        <code>/etc/webcafeina-migrator/env</code>, luego{" "}
        <code>systemctl restart webcafeina-api webcafeina-worker</code>.
      </p>
    </div>
  );
}
