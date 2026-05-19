"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

import {
  DEFAULT_THEME,
  type EmailLayoutTheme,
  ThemeEditorForm,
} from "./theme-editor-form";

interface EmailLayoutRead {
  id: number;
  layout_html: string;
  layout_css: string;
  theme_config: EmailLayoutTheme | null;
  updated_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

interface EmailLayoutEditorProps {
  initialLayout: EmailLayoutRead;
}

type Mode = "visual" | "code";

/**
 * Editor del singleton `email_layouts`. v0.15.0:
 *
 * - Tab "Visual" (default si `theme_config` no es null): form con
 *   colores, branding, tipografía, espaciado y bordes que regenera
 *   HTML+CSS server-side al guardar.
 * - Tab "Código" (fallback experto): dos textareas font-mono para
 *   HTML+CSS crudos. Al guardar desde Código se PIERDE el tema
 *   (`theme_config=NULL`) y el tab Visual queda deshabilitado hasta
 *   "Restaurar valores por defecto".
 *
 * El iframe LivePreview es compartido por ambos tabs:
 * - Modo Visual lo alimenta con el resultado del POST /preview que
 *   hace el form a cada cambio (debounce 600ms).
 * - Modo Código lo alimenta con sustitución naive client-side (mismo
 *   patrón que pre-v0.15.0 — la única vía sin pasar por backend).
 */
export function EmailLayoutEditor({ initialLayout }: EmailLayoutEditorProps) {
  const router = useRouter();
  const themeAvailable = initialLayout.theme_config !== null;
  const [mode, setMode] = useState<Mode>(themeAvailable ? "visual" : "code");

  // Estado de preview compartido entre tabs.
  const [preview, setPreview] = useState<{
    html: string;
    css: string;
  }>({ html: initialLayout.layout_html, css: initialLayout.layout_css });

  // Modo Código: estado local de los textareas.
  const [codeHtml, setCodeHtml] = useState(initialLayout.layout_html);
  const [codeCss, setCodeCss] = useState(initialLayout.layout_css);
  const [codePending, codeStartTransition] = useTransition();
  const [codeError, setCodeError] = useState<string | null>(null);

  // Estado del flag "tema activo" (tras guardar desde Visual pasa a true;
  // tras guardar desde Código pasa a false).
  const [themeActive, setThemeActive] = useState(themeAvailable);

  // Confirmación inline del botón "Restaurar valores por defecto"
  // (sustituye a window.confirm que algunos navegadores bloquean).
  const [resetConfirming, setResetConfirming] = useState(false);

  function handleVisualSaved(savedTheme: EmailLayoutTheme) {
    setThemeActive(true);
    // Re-sincronizar estado de Código con el HTML/CSS regenerado.
    setCodeHtml(preview.html);
    setCodeCss(preview.css);
    router.refresh();
    // Evitar warning "savedTheme not used".
    void savedTheme;
  }

  function handleVisualPreview(
    p: { layout_html: string; layout_css: string } | null,
  ) {
    if (p) setPreview({ html: p.layout_html, css: p.layout_css });
  }

  function handleCodeSave() {
    setCodeError(null);
    codeStartTransition(async () => {
      try {
        await api.put("/api/v1/email-layout", {
          layout_html: codeHtml,
          layout_css: codeCss,
        });
        toast.success(
          themeActive
            ? "Layout guardado. El tema visual se ha desactivado — para reactivarlo: Restaurar valores por defecto."
            : "Layout guardado.",
        );
        setThemeActive(false);
        router.refresh();
      } catch (err) {
        setCodeError(err instanceof ApiError ? err.message : "Error al guardar");
      }
    });
  }

  function handleResetClick() {
    // Primer click: pide confirmación inline (cambia el copy del botón).
    if (!resetConfirming) {
      setResetConfirming(true);
      // Auto-cancel tras 5 s si el operador no confirma.
      window.setTimeout(() => setResetConfirming(false), 5000);
      return;
    }
    // Segundo click: ejecuta el PUT.
    setResetConfirming(false);
    codeStartTransition(async () => {
      try {
        await api.put("/api/v1/email-layout", { theme_config: DEFAULT_THEME });
        toast.success("Tema restaurado al default Webcafeína.");
        setThemeActive(true);
        setMode("visual");
        router.refresh();
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Error al restaurar");
      }
    });
  }

  return (
    <div className="space-y-4">
      <div
        role="tablist"
        aria-label="Modo de edición del layout"
        className="flex gap-1 border-b border-wcm-detail/40 text-[10.5px] uppercase tracking-wider"
      >
        <TabBtn
          active={mode === "visual"}
          disabled={!themeActive}
          onClick={() => setMode("visual")}
          title={
            themeActive
              ? undefined
              : "El layout fue editado manualmente (modo Código). Restaura el tema por defecto para activar el modo Visual."
          }
        >
          Visual
        </TabBtn>
        <TabBtn
          active={mode === "code"}
          onClick={() => setMode("code")}
        >
          Código
        </TabBtn>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_540px]">
        <div className="space-y-3">
          {mode === "visual" && themeActive && (
            <ThemeEditorForm
              initialTheme={initialLayout.theme_config ?? DEFAULT_THEME}
              onSaved={handleVisualSaved}
              onPreview={handleVisualPreview}
            />
          )}

          {mode === "visual" && !themeActive && (
            <div className="space-y-3 rounded-sm border border-wcm-warning/40 bg-wcm-warning/10 p-4 text-xs text-wcm-text/90">
              <p className="font-semibold text-wcm-warning">
                Modo Visual deshabilitado
              </p>
              <p>
                El layout fue editado manualmente (HTML/CSS crudo). El editor
                visual no puede inferir un tema desde código personalizado. Para
                reactivar el modo Visual, restaura el tema por defecto
                Webcafeína (perderás los cambios manuales).
              </p>
              <button
                type="button"
                onClick={handleResetClick}
                disabled={codePending}
                className={cn(
                  "rounded-sm border px-3 py-1 text-xs font-semibold hover:brightness-110 disabled:opacity-50",
                  resetConfirming
                    ? "border-wcm-danger bg-wcm-danger/20 text-wcm-danger"
                    : "border-wcm-warning bg-wcm-warning/20 text-wcm-warning",
                )}
              >
                {codePending
                  ? "Restaurando…"
                  : resetConfirming
                    ? "Pulsa otra vez para confirmar"
                    : "Restaurar tema por defecto"}
              </button>
            </div>
          )}

          {mode === "code" && (
            <div className="space-y-3 text-xs">
              {themeActive && (
                <div className="rounded-sm border border-wcm-warning/40 bg-wcm-warning/10 p-2 text-[11px] text-wcm-warning">
                  Tu layout tiene un tema visual activo. Si guardas desde aquí,
                  el tema se desactivará y deberás restaurarlo para volver al
                  modo Visual.
                </div>
              )}
              <Field htmlFor="layout-html" label="HTML Jinja2 (slot {{ content | safe }})">
                <textarea
                  id="layout-html"
                  value={codeHtml}
                  onChange={(e) => setCodeHtml(e.target.value)}
                  disabled={codePending}
                  rows={20}
                  spellCheck={false}
                  className="w-full resize-y rounded-sm border border-wcm-detail/70 bg-wcm-primary p-2 font-mono text-[11px] leading-relaxed text-wcm-text focus:border-wcm-accent focus:outline-none disabled:opacity-50"
                />
              </Field>
              <Field htmlFor="layout-css" label="CSS (premailer lo inlinea al enviar)">
                <textarea
                  id="layout-css"
                  value={codeCss}
                  onChange={(e) => setCodeCss(e.target.value)}
                  disabled={codePending}
                  rows={14}
                  spellCheck={false}
                  className="w-full resize-y rounded-sm border border-wcm-detail/70 bg-wcm-primary p-2 font-mono text-[11px] leading-relaxed text-wcm-text focus:border-wcm-accent focus:outline-none disabled:opacity-50"
                />
              </Field>
              {codeError && (
                <div className="rounded-sm border border-wcm-danger/40 bg-wcm-danger/10 p-2 text-[11px] text-wcm-danger">
                  {codeError}
                </div>
              )}
              <div className="flex justify-between gap-2">
                <button
                  type="button"
                  onClick={handleResetClick}
                  disabled={codePending}
                  className={cn(
                    "rounded-sm border px-3 py-1 text-xs hover:brightness-110 disabled:opacity-50",
                    resetConfirming
                      ? "border-wcm-danger bg-wcm-danger/20 text-wcm-danger font-semibold"
                      : "border-wcm-detail/60 text-wcm-text/80 hover:border-wcm-detail hover:text-wcm-text",
                  )}
                >
                  {codePending
                    ? "Restaurando…"
                    : resetConfirming
                      ? "Pulsa otra vez para confirmar"
                      : "Restaurar valores por defecto"}
                </button>
                <button
                  type="button"
                  onClick={handleCodeSave}
                  disabled={codePending}
                  className={cn(
                    "rounded-sm bg-wcm-accent px-3 py-1 text-xs font-semibold text-wcm-primary transition-colors hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50",
                  )}
                >
                  {codePending ? "Guardando…" : "Guardar (código) →"}
                </button>
              </div>
            </div>
          )}
        </div>

        <LivePreview
          html={mode === "code" ? codeHtml : preview.html}
          css={mode === "code" ? codeCss : preview.css}
        />
      </div>
    </div>
  );
}

function TabBtn({
  active,
  disabled,
  onClick,
  title,
  children,
}: {
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
  title?: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      aria-disabled={disabled}
      disabled={disabled}
      onClick={onClick}
      title={title}
      className={cn(
        "px-3 py-1.5 transition-colors",
        disabled && "cursor-not-allowed opacity-50",
        !disabled && active
          ? "border-b-2 border-wcm-accent text-wcm-accent"
          : "text-muted-foreground hover:text-wcm-text",
      )}
    >
      {children}
    </button>
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

/**
 * Preview local del HTML+CSS en un iframe. Sustituye `{{ var }}`
 * naive con un stub mínimo para que el operador vea algo realista.
 *
 * NO aplica premailer (el backend lo hace al enviar). Diferencias
 * mínimas posibles. Para preview exacto, guarda y abre una plantilla
 * desde `/settings/templates`.
 */
function LivePreview({ html, css }: { html: string; css: string }) {
  const stub = {
    content:
      "<p>Hola Restaurante Demo,</p><p>Soy <strong>Webcafeína</strong> — un saludo desde el preview en vivo.</p>",
    cta_label: "Reservar 20 min",
    cta_url: "https://cal.com/webcafeina",
    logo_url: "",
    company_legal_name: "Webcafeína S.L.",
    company_cif: "B10463990",
    company_address: "Cáceres",
    company_contact_email: "info@webcafeina.com",
    privacy_policy_url: "https://webcafeina.com/politica-de-privacidad",
    opt_out_url: "https://migrator.webcafeina.com/opt-out?token=PREVIEW",
    subject: "Vista previa demo",
  };

  let rendered = html;
  for (const [k, v] of Object.entries(stub)) {
    rendered = rendered.replaceAll(
      new RegExp(`\\{\\{\\s*${k}(\\s*\\|\\s*\\w+)?\\s*\\}\\}`, "g"),
      String(v),
    );
  }
  // Limpiar {% if/endif %} naive — preview aproximado.
  rendered = rendered.replace(/\{%[^}]*%\}/g, "");
  const doc = rendered.includes("</head>")
    ? rendered.replace("</head>", `<style>${css}</style></head>`)
    : `<style>${css}</style>${rendered}`;

  return (
    <div className="sticky top-4 space-y-1">
      <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
        Vista previa
      </div>
      <iframe
        title="Vista previa del layout maestro"
        aria-label="Vista previa del layout maestro"
        sandbox="allow-same-origin"
        srcDoc={doc}
        className="w-full rounded-sm border border-wcm-detail/40 bg-white"
        style={{ height: 720 }}
      />
      <p className="text-[10px] text-muted-foreground">
        Preview aproximado (sin premailer, con stub naive de variables).
        Para validar exactamente lo que llegará al lead, usa
        <code className="mx-1">test-send</code> desde el detalle del lead.
      </p>
    </div>
  );
}
