"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

interface EmailLayoutRead {
  id: number;
  layout_html: string;
  layout_css: string;
  updated_by_user_id: number | null;
  created_at: string;
  updated_at: string;
}

interface EmailLayoutEditorProps {
  initialLayout: EmailLayoutRead;
}

/**
 * Editor del singleton `email_layouts`. Layout 2-col:
 *  - Izquierda: dos textareas font-mono (HTML, CSS).
 *  - Derecha: iframe en vivo con un preview local (no fetcha al
 *    backend; mete el CSS en `<style>` dentro del HTML y lo pinta).
 *    Debounce 600 ms para no relayoutear en cada tecla.
 *
 * Al guardar: PUT al backend. Valida sintaxis Jinja2 (422 si rota).
 * Si la PATCH tarda más de 500 ms muestra spinner.
 */
export function EmailLayoutEditor({ initialLayout }: EmailLayoutEditorProps) {
  const router = useRouter();
  const [html, setHtml] = useState(initialLayout.layout_html);
  const [css, setCss] = useState(initialLayout.layout_css);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const dirty =
    html !== initialLayout.layout_html || css !== initialLayout.layout_css;

  function handleSave() {
    setError(null);
    startTransition(async () => {
      try {
        await api.put<EmailLayoutRead>("/api/v1/email-layout", {
          layout_html: html,
          layout_css: css,
        });
        toast.success("Layout guardado. Los próximos correos usarán esta versión.");
        router.refresh();
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : "Error al guardar";
        setError(msg);
      }
    });
  }

  function handleReset() {
    setHtml(initialLayout.layout_html);
    setCss(initialLayout.layout_css);
    setError(null);
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_1fr]">
        <div className="space-y-3">
          <Field htmlFor="layout-html" label="HTML Jinja2 (slot {{ content | safe }})">
            <textarea
              id="layout-html"
              value={html}
              onChange={(e) => setHtml(e.target.value)}
              disabled={pending}
              rows={20}
              spellCheck={false}
              className="w-full resize-y rounded-sm border border-wcm-detail/70 bg-wcm-primary p-2 font-mono text-[11px] leading-relaxed text-wcm-text focus:border-wcm-accent focus:outline-none disabled:opacity-50"
            />
          </Field>
          <Field htmlFor="layout-css" label="CSS (premailer lo inlinea al enviar)">
            <textarea
              id="layout-css"
              value={css}
              onChange={(e) => setCss(e.target.value)}
              disabled={pending}
              rows={14}
              spellCheck={false}
              className="w-full resize-y rounded-sm border border-wcm-detail/70 bg-wcm-primary p-2 font-mono text-[11px] leading-relaxed text-wcm-text focus:border-wcm-accent focus:outline-none disabled:opacity-50"
            />
          </Field>
        </div>

        <LivePreview html={html} css={css} />
      </div>

      {error && (
        <div className="rounded-sm border border-wcm-danger/40 bg-wcm-danger/10 p-2 text-[11px] text-wcm-danger">
          {error}
        </div>
      )}

      <footer className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-[11px] text-muted-foreground">
          {dirty
            ? "Cambios sin guardar."
            : `Última actualización: ${new Date(initialLayout.updated_at).toLocaleString("es-ES")}`}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleReset}
            disabled={pending || !dirty}
            className="rounded-sm border border-wcm-detail/60 px-3 py-1 text-xs text-wcm-text/80 hover:border-wcm-detail hover:text-wcm-text disabled:opacity-50"
          >
            Descartar cambios
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={pending || !dirty}
            className={cn(
              "rounded-sm bg-wcm-accent px-3 py-1 text-xs font-semibold text-wcm-primary transition-colors hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50",
            )}
          >
            {pending ? "Guardando…" : "Guardar layout →"}
          </button>
        </div>
      </footer>
    </div>
  );
}

/**
 * Preview local del layout sin pasar por el backend: junta HTML + CSS
 * + un contexto mockeado mínimo en el slot `{{ content | safe }}` y
 * lo pinta en iframe. Útil para iterar visualmente sin tocar BD.
 *
 * NO aplica premailer (eso lo hace el backend al enviar). El layout
 * en el cliente final puede verse ligeramente distinto.
 */
function LivePreview({ html, css }: { html: string; css: string }) {
  const [doc, setDoc] = useState("");
  const timeout = useRef<number | null>(null);

  const stub = useMemo(
    () => ({
      content: "<p><strong>Demo:</strong> aquí va el cuerpo de la plantilla.</p>",
      cta_label: "Ver propuesta",
      cta_url: "https://webcafeina.com",
      logo_url: "",
      company_legal_name: "Webcafeína S.L.",
      company_cif: "B10463990",
      company_address: "Cáceres, España",
      company_contact_email: "info@webcafeina.com",
      privacy_policy_url: "https://webcafeina.com/politica-de-privacidad",
      opt_out_url: "https://migrator.webcafeina.com/opt-out?token=PREVIEW",
      subject: "Asunto demo",
    }),
    [],
  );

  useEffect(() => {
    if (timeout.current) window.clearTimeout(timeout.current);
    timeout.current = window.setTimeout(() => {
      try {
        // Render naive: substituimos `{{ var }}` por valores del stub
        // y `{% if x %}...{% endif %}` por el contenido si x es truthy.
        // No es Jinja2 real (el backend tiene el motor); este preview
        // es solo para iterar visualmente. Las construcciones
        // complejas pueden NO renderizar igual — usa "Guardar" + ve
        // la preview real desde /settings/templates con una plantilla.
        let rendered = html;
        for (const [k, v] of Object.entries(stub)) {
          rendered = rendered.replaceAll(
            new RegExp(`\\{\\{\\s*${k}(\\s*\\|\\s*\\w+)?\\s*\\}\\}`, "g"),
            String(v),
          );
        }
        // Quitamos cualquier `{% ... %}` residual para no ensuciar
        // visualmente. Sustituimos por string vacía.
        rendered = rendered.replace(/\{%[^}]*%\}/g, "");

        // Inyectar CSS en <head> o al inicio.
        const withCss = rendered.includes("</head>")
          ? rendered.replace("</head>", `<style>${css}</style></head>`)
          : `<style>${css}</style>${rendered}`;
        setDoc(withCss);
      } catch {
        setDoc("");
      }
    }, 600);
    return () => {
      if (timeout.current) window.clearTimeout(timeout.current);
    };
  }, [html, css, stub]);

  return (
    <div className="space-y-1">
      <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
        Vista previa local (sin premailer)
      </div>
      <iframe
        title="Vista previa del layout maestro"
        aria-label="Vista previa del layout maestro"
        sandbox="allow-same-origin"
        srcDoc={doc}
        className="w-full rounded-sm border border-wcm-detail/40 bg-white"
        style={{ height: 600 }}
      />
      <p className="text-[10px] text-muted-foreground">
        Preview naive (sustituye <code>{"{{ var }}"}</code> sin Jinja2 real).
        Para validar el render exacto, guarda y abre cualquier plantilla
        en <code>/settings/templates</code> &rarr; pestaña Vista previa.
      </p>
    </div>
  );
}

function Field({
  htmlFor,
  label,
  children,
}: {
  htmlFor: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={htmlFor}
        className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground"
      >
        {label}
      </label>
      {children}
    </div>
  );
}
