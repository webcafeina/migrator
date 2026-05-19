import Link from "next/link";

import { api, ApiError } from "@/lib/api";

import { EmailLayoutEditor } from "./_components/email-layout-editor";
import type { EmailLayoutTheme } from "./_components/theme-editor-form";

interface EmailLayoutRead {
  id: number;
  layout_html: string;
  layout_css: string;
  /** v0.15.0 — si poblado, el tab Visual está habilitado y precarga
   *  estos valores. Si NULL, el operador editó código a mano y debe
   *  hacer "Restaurar valores por defecto" para reactivar Visual. */
  theme_config: EmailLayoutTheme | null;
  updated_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * `/settings/email-layout` — editor de la shell HTML maestra que
 * envuelve TODOS los correos de outreach (v0.14.0). Solo admin (el
 * backend valida; la UI deja al operador intentar y recibir 403).
 *
 * El layout es un singleton (`id=1`); este Server Component lo fetcha
 * y lo pasa al Client editor. Si la tabla está vacía (migración no
 * aplicada) mostramos un placeholder explicativo.
 */
export default async function EmailLayoutPage() {
  let layout: EmailLayoutRead | null = null;
  let loadError: string | null = null;
  try {
    layout = await api.get<EmailLayoutRead>("/api/v1/email-layout");
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      loadError = err.message;
    } else {
      loadError =
        err instanceof Error
          ? err.message
          : "Error al cargar el layout";
    }
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold text-wcm-text">
            Layout maestro del correo
          </h1>
          <p className="text-xs text-muted-foreground">
            Shell HTML + CSS que envuelve cada plantilla de contacto.
            El composer inyecta el cuerpo de la plantilla en el slot{" "}
            <code>{"{{ content | safe }}"}</code>, aplica premailer
            (inlinea CSS) y envía el resultado.
          </p>
        </div>
        <Link
          href="/settings"
          className="text-xs text-wcm-text/70 hover:text-wcm-accent"
        >
          ← Volver a Ajustes
        </Link>
      </header>

      {layout ? (
        <EmailLayoutEditor initialLayout={layout} />
      ) : (
        <div className="rounded-sm border border-wcm-danger/40 bg-wcm-danger/10 p-4 text-xs text-wcm-danger">
          <p className="font-semibold">Layout no inicializado</p>
          <p className="mt-1 text-wcm-text/80">
            {loadError ??
              "El singleton `email_layouts` no existe todavía. Aplica la migración 0005 (`alembic upgrade head`)."}
          </p>
        </div>
      )}

      <p className="text-[10.5px] text-muted-foreground">
        Solo administradores pueden editar el layout maestro. Los
        cambios NO son retroactivos: las sequences ya enviadas
        conservan su snapshot HTML en{" "}
        <code>outreach_sends.body_html_rendered</code>; solo los nuevos
        correos usarán esta versión.
      </p>
    </div>
  );
}
