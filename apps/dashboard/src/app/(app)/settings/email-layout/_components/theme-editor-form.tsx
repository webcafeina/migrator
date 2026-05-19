"use client";

import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import { toast } from "sonner";

import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";

import { ColorField } from "./color-field";

/**
 * Shape del tema persistido en `email_layouts.theme_config`. Refleja
 * 1:1 el schema pydantic `EmailLayoutTheme` del backend.
 */
export interface EmailLayoutTheme {
  // Colores
  cta_bg: string;
  cta_text: string;
  cta_border: string;
  page_bg: string;
  card_bg: string;
  card_border: string;
  text_color: string;
  text_strong: string;
  link_color: string;
  footer_text: string;
  brand_accent: string;
  // Branding
  show_logo: boolean;
  logo_url_override: string | null;
  logo_max_width_px: number;
  // Tipografía
  font_family: "system-ui" | "serif" | "Inter";
  body_font_size_px: number;
  body_line_height: number;
  brand_text_size_px: number;
  // Espaciado y dimensiones
  card_max_width_px: number;
  content_padding_px: number;
  header_padding_px: number;
  footer_padding_px: number;
  // Bordes
  card_border_radius_px: number;
  cta_border_radius_px: number;
  card_border_width_px: number;
}

/**
 * Defaults Webcafeína — espejo de `default_theme()` del backend.
 * Se usan al "Reset al tema por defecto" y al hidratar el form si
 * el layout tenía theme_config=null.
 */
export const DEFAULT_THEME: EmailLayoutTheme = {
  cta_bg: "#B1F100",
  cta_text: "#0E1218",
  cta_border: "#94C800",
  page_bg: "#F5F6F8",
  card_bg: "#FFFFFF",
  card_border: "#E5E7EB",
  text_color: "#1F2937",
  text_strong: "#0E1218",
  link_color: "#5A8A00",
  footer_text: "#6B7280",
  brand_accent: "#5A8A00",
  show_logo: true,
  logo_url_override: null,
  logo_max_width_px: 160,
  font_family: "system-ui",
  body_font_size_px: 15,
  body_line_height: 1.65,
  brand_text_size_px: 22,
  card_max_width_px: 600,
  content_padding_px: 28,
  header_padding_px: 28,
  footer_padding_px: 18,
  card_border_radius_px: 6,
  cta_border_radius_px: 4,
  card_border_width_px: 1,
};

interface ThemeEditorFormProps {
  /** Tema inicial hidratado del backend (o defaults si era NULL). */
  initialTheme: EmailLayoutTheme;
  /** Callback al guardar exitosamente, recibe el tema persistido. */
  onSaved: (theme: EmailLayoutTheme) => void;
  /** Callback que recibe el HTML generado server-side cada vez que
   *  cambia el tema (con debounce 600ms) — alimenta el LivePreview. */
  onPreview: (preview: { layout_html: string; layout_css: string } | null) => void;
}

/**
 * Form visual del layout maestro. ~24 controles agrupados en 5
 * secciones (Colores / Branding / Tipografía / Espaciado / Bordes).
 *
 * Comportamiento:
 * - Cada cambio dispara POST `/email-layout/preview` con debounce 600 ms
 *   y AbortController para cancelar requests obsoletos.
 * - Botón "Guardar tema" hace PUT `/email-layout` con `theme_config`.
 * - Botón "Restaurar valores por defecto" resetea el form sin guardar.
 */
export function ThemeEditorForm({
  initialTheme,
  onSaved,
  onPreview,
}: ThemeEditorFormProps) {
  const [theme, setTheme] = useState<EmailLayoutTheme>(initialTheme);
  const [pending, startTransition] = useTransition();
  const [saveError, setSaveError] = useState<string | null>(null);
  const debounceRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const dirty = useMemo(
    () => JSON.stringify(theme) !== JSON.stringify(initialTheme),
    [theme, initialTheme],
  );

  function update<K extends keyof EmailLayoutTheme>(
    key: K,
    value: EmailLayoutTheme[K],
  ) {
    setTheme((prev) => ({ ...prev, [key]: value }));
  }

  // Debounce + AbortController del preview en vivo.
  useEffect(() => {
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => {
      if (abortRef.current) abortRef.current.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      api
        .post<{ layout_html: string; layout_css: string }>(
          "/api/v1/email-layout/preview",
          theme,
          { signal: controller.signal },
        )
        .then((res) => onPreview(res))
        .catch((err) => {
          if (err instanceof DOMException && err.name === "AbortError") return;
          // Si falla, no rompemos el form — solo limpiamos el preview.
          onPreview(null);
        });
    }, 600);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
  }, [theme, onPreview]);

  function handleSave() {
    setSaveError(null);
    startTransition(async () => {
      try {
        await api.put("/api/v1/email-layout", { theme_config: theme });
        toast.success("Tema guardado. Los próximos correos usarán esta versión.");
        onSaved(theme);
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : "Error al guardar";
        setSaveError(msg);
      }
    });
  }

  function handleReset() {
    setTheme(DEFAULT_THEME);
    setSaveError(null);
  }

  return (
    <div className="space-y-5 text-xs">
      <Section title="Colores · CTA">
        <Grid cols={3}>
          <ColorField
            label="Botón fondo"
            value={theme.cta_bg}
            onChange={(v) => update("cta_bg", v)}
            disabled={pending}
            hint="Acento de marca"
          />
          <ColorField
            label="Botón texto"
            value={theme.cta_text}
            onChange={(v) => update("cta_text", v)}
            disabled={pending}
          />
          <ColorField
            label="Botón borde"
            value={theme.cta_border}
            onChange={(v) => update("cta_border", v)}
            disabled={pending}
          />
        </Grid>
      </Section>

      <Section title="Colores · Fondo y texto">
        <Grid cols={3}>
          <ColorField
            label="Fondo página"
            value={theme.page_bg}
            onChange={(v) => update("page_bg", v)}
            disabled={pending}
            hint="Wrapper exterior"
          />
          <ColorField
            label="Fondo card"
            value={theme.card_bg}
            onChange={(v) => update("card_bg", v)}
            disabled={pending}
            hint="Bloque central"
          />
          <ColorField
            label="Borde card"
            value={theme.card_border}
            onChange={(v) => update("card_border", v)}
            disabled={pending}
          />
          <ColorField
            label="Texto principal"
            value={theme.text_color}
            onChange={(v) => update("text_color", v)}
            disabled={pending}
          />
          <ColorField
            label="Texto destacado"
            value={theme.text_strong}
            onChange={(v) => update("text_strong", v)}
            disabled={pending}
            hint="<strong> y títulos"
          />
          <ColorField
            label="Links"
            value={theme.link_color}
            onChange={(v) => update("link_color", v)}
            disabled={pending}
          />
          <ColorField
            label="Acento marca"
            value={theme.brand_accent}
            onChange={(v) => update("brand_accent", v)}
            disabled={pending}
            hint="'í' de webcafeína"
          />
          <ColorField
            label="Texto footer"
            value={theme.footer_text}
            onChange={(v) => update("footer_text", v)}
            disabled={pending}
          />
        </Grid>
      </Section>

      <Section title="Branding">
        <div className="space-y-3">
          <label className="flex items-center gap-2 text-[11px]">
            <input
              type="checkbox"
              checked={theme.show_logo}
              onChange={(e) => update("show_logo", e.target.checked)}
              disabled={pending}
              className="h-3.5 w-3.5"
            />
            <span>
              <strong>Mostrar logo</strong> en el header. Si no, pinta
              "webcafeína" como texto estilado.
            </span>
          </label>
          {theme.show_logo && (
            <Grid cols={2}>
              <Field label="URL alternativa del logo (opcional)">
                <input
                  type="url"
                  value={theme.logo_url_override ?? ""}
                  onChange={(e) =>
                    update("logo_url_override", e.target.value || null)
                  }
                  disabled={pending}
                  placeholder="https://… (vacío = EMAIL_LOGO_URL del env)"
                  maxLength={500}
                  className={inputClass}
                />
              </Field>
              <Field label="Ancho máximo del logo (px)">
                <NumberInput
                  value={theme.logo_max_width_px}
                  onChange={(v) => update("logo_max_width_px", v)}
                  min={80}
                  max={400}
                  disabled={pending}
                />
              </Field>
            </Grid>
          )}
        </div>
      </Section>

      <Section title="Tipografía">
        <Grid cols={4}>
          <Field label="Fuente">
            <select
              value={theme.font_family}
              onChange={(e) =>
                update(
                  "font_family",
                  e.target.value as EmailLayoutTheme["font_family"],
                )
              }
              disabled={pending}
              className={inputClass}
            >
              <option value="system-ui">system-ui (default)</option>
              <option value="serif">serif (Georgia)</option>
              <option value="Inter">Inter</option>
            </select>
          </Field>
          <Field label="Texto body (px)">
            <NumberInput
              value={theme.body_font_size_px}
              onChange={(v) => update("body_font_size_px", v)}
              min={12}
              max={20}
              disabled={pending}
            />
          </Field>
          <Field label="Interlineado">
            <NumberInput
              value={theme.body_line_height}
              onChange={(v) => update("body_line_height", v)}
              min={1.2}
              max={2.2}
              step={0.05}
              disabled={pending}
            />
          </Field>
          <Field label='"webcafeína" header (px)'>
            <NumberInput
              value={theme.brand_text_size_px}
              onChange={(v) => update("brand_text_size_px", v)}
              min={14}
              max={32}
              disabled={pending}
            />
          </Field>
        </Grid>
      </Section>

      <Section title="Espaciado">
        <Grid cols={4}>
          <Field label="Ancho del card (px)">
            <NumberInput
              value={theme.card_max_width_px}
              onChange={(v) => update("card_max_width_px", v)}
              min={320}
              max={720}
              disabled={pending}
            />
          </Field>
          <Field label="Padding contenido">
            <NumberInput
              value={theme.content_padding_px}
              onChange={(v) => update("content_padding_px", v)}
              min={8}
              max={64}
              disabled={pending}
            />
          </Field>
          <Field label="Padding header">
            <NumberInput
              value={theme.header_padding_px}
              onChange={(v) => update("header_padding_px", v)}
              min={8}
              max={64}
              disabled={pending}
            />
          </Field>
          <Field label="Padding footer">
            <NumberInput
              value={theme.footer_padding_px}
              onChange={(v) => update("footer_padding_px", v)}
              min={8}
              max={64}
              disabled={pending}
            />
          </Field>
        </Grid>
      </Section>

      <Section title="Bordes">
        <Grid cols={3}>
          <Field label="Radius card (px)">
            <NumberInput
              value={theme.card_border_radius_px}
              onChange={(v) => update("card_border_radius_px", v)}
              min={0}
              max={12}
              disabled={pending}
            />
          </Field>
          <Field label="Radius CTA (px)">
            <NumberInput
              value={theme.cta_border_radius_px}
              onChange={(v) => update("cta_border_radius_px", v)}
              min={0}
              max={12}
              disabled={pending}
            />
          </Field>
          <Field label="Grosor borde card (px)">
            <NumberInput
              value={theme.card_border_width_px}
              onChange={(v) => update("card_border_width_px", v)}
              min={0}
              max={4}
              disabled={pending}
            />
          </Field>
        </Grid>
      </Section>

      {saveError && (
        <div className="rounded-sm border border-wcm-danger/40 bg-wcm-danger/10 p-2 text-[11px] text-wcm-danger">
          {saveError}
        </div>
      )}

      <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-wcm-detail/30 pt-3">
        <div className="text-[11px] text-muted-foreground">
          {dirty ? "Cambios sin guardar." : "Sin cambios."}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleReset}
            disabled={pending}
            className="rounded-sm border border-wcm-detail/60 px-3 py-1 text-xs text-wcm-text/80 hover:border-wcm-detail hover:text-wcm-text disabled:opacity-50"
          >
            Restaurar valores por defecto
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={pending || !dirty}
            className={cn(
              "rounded-sm bg-wcm-accent px-3 py-1 text-xs font-semibold text-wcm-primary transition-colors hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50",
            )}
          >
            {pending ? "Guardando…" : "Guardar tema →"}
          </button>
        </div>
      </footer>
    </div>
  );
}

const inputClass =
  "h-7 w-full rounded-sm border border-wcm-detail/70 bg-wcm-primary px-2 text-[11px] text-wcm-text placeholder:text-muted-foreground focus:border-wcm-accent focus:outline-none disabled:opacity-50";

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <h3 className="text-[10.5px] font-semibold uppercase tracking-[0.1em] text-wcm-accent">
        {title}
      </h3>
      {children}
    </section>
  );
}

function Grid({
  cols,
  children,
}: {
  cols: 2 | 3 | 4;
  children: React.ReactNode;
}) {
  const cls = {
    2: "grid grid-cols-1 gap-3 sm:grid-cols-2",
    3: "grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3",
    4: "grid grid-cols-2 gap-3 md:grid-cols-4",
  }[cols];
  return <div className={cls}>{children}</div>;
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
        {label}
      </span>
      {children}
    </div>
  );
}

function NumberInput({
  value,
  onChange,
  min,
  max,
  step = 1,
  disabled,
}: {
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step?: number;
  disabled?: boolean;
}) {
  return (
    <input
      type="number"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => {
        const n = Number(e.target.value);
        if (Number.isFinite(n)) onChange(n);
      }}
      disabled={disabled}
      className={cn(inputClass, "tabular-nums")}
    />
  );
}
