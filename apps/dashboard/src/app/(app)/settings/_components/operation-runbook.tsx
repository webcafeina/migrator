/**
 * Runbook condensado para operaciones que NO viven en el dashboard:
 * edición de variables del sistema (SSH al servidor) y gestión de
 * usuarios (CLI `wcm users`). Sustituye los placeholders previos —
 * incluyendo la mentira "UI de gestión: Fase 14" — por información
 * accionable.
 *
 * Presentacional puro, sin datos dinámicos. Si en algún momento se
 * añade UI de gestión de usuarios, este componente se reduce o
 * desaparece.
 */
export function OperationRunbook() {
  return (
    <div className="space-y-5 rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-4 text-xs">
      <Section
        title="editar variables del sistema"
        intro={
          <>
            El dashboard es solo lectura para configuración. Las variables
            viven en <code>.env</code> en el servidor (permisos 600).
          </>
        }
      >
        <Step n={1}>
          SSH al servidor:{" "}
          <code className="text-wcm-text">
            ssh root@migrator.webcafeina.com
          </code>
        </Step>
        <Step n={2}>
          Editar{" "}
          <code className="text-wcm-text">/etc/webcafeina-migrator/env</code>
        </Step>
        <Step n={3}>
          Reload de servicios afectados:{" "}
          <code className="text-wcm-text">
            systemctl restart webcafeina-api webcafeina-worker
          </code>
        </Step>
        <Note>
          Detalle completo del despliegue en{" "}
          <span className="text-wcm-text">docs/despliegue.md</span>.
        </Note>
      </Section>

      <Section
        title="gestionar usuarios (admin)"
        intro={
          <>
            Crear, listar, cambiar rol o eliminar — todo vía CLI{" "}
            <code className="text-wcm-text">wcm users</code> en el
            servidor. No hay UI prevista; el volumen de usuarios del
            equipo Webcafeína (9 personas) no justifica el coste.
          </>
        }
      >
        <Step n={1}>
          Listar:{" "}
          <code className="text-wcm-text">wcm users list</code>
        </Step>
        <Step n={2}>
          Crear:{" "}
          <code className="text-wcm-text">
            wcm users create --email NOMBRE@webcafeina.com --role operator
          </code>
        </Step>
        <Step n={3}>
          Cambiar rol:{" "}
          <code className="text-wcm-text">
            wcm users set-role EMAIL --role admin
          </code>
        </Step>
        <Note>
          Roles disponibles:{" "}
          <code className="text-wcm-text">admin</code> ·{" "}
          <code className="text-wcm-text">operator</code> ·{" "}
          <code className="text-wcm-text">viewer</code>.
        </Note>
      </Section>
    </div>
  );
}

function Section({
  title,
  intro,
  children,
}: {
  title: string;
  intro: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <h3 className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
        {title}
      </h3>
      <p className="text-wcm-text/80">{intro}</p>
      <ol className="space-y-1.5">{children}</ol>
    </div>
  );
}

function Step({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <li className="flex gap-2 text-wcm-text/90">
      <span className="shrink-0 tabular-nums text-wcm-accent">{n}.</span>
      <span className="break-all">{children}</span>
    </li>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <p className="border-t border-wcm-detail/30 pt-2 text-[11px] text-muted-foreground">
      {children}
    </p>
  );
}
