"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";

import { ApiError, api } from "@/lib/api";
import { cn, formatRelativeTime } from "@/lib/utils";

interface TemplateRead {
  id: number;
  name: string;
  subject_template: string;
  body_template: string;
  language: string;
  created_at: string;
  updated_at: string;
}

interface TemplateManagerProps {
  initialTemplates: TemplateRead[];
}

type Mode =
  | { kind: "view"; tplId: number | null }
  | { kind: "edit"; tpl: TemplateRead }
  | { kind: "create" };

/**
 * Pantalla CRUD de plantillas de contacto. Layout master-detail
 * simple: lista a la izquierda con click para ver / editar; panel
 * derecho con form (create o edit) o vista del template seleccionado.
 *
 * El Server Component padre (`page.tsx`) fetcha el listado inicial y
 * lo pasa aquí. Tras cualquier mutación llamamos `router.refresh()`
 * para que el Server vuelva a fetchar.
 *
 * RBAC backend: lectura any_user, escritura admin only. La UI no
 * gestiona la guardia (si el operador intenta crear/editar verá 403
 * del backend); decisión consciente para no acoplar UI a un context
 * de role que aún no existe.
 */
export function TemplateManager({ initialTemplates }: TemplateManagerProps) {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>({ kind: "view", tplId: null });
  const [pending, startTransition] = useTransition();
  const templates = initialTemplates;

  // ---- Ayudantes de selección ----

  const selectedTpl =
    mode.kind === "edit"
      ? mode.tpl
      : mode.kind === "view" && mode.tplId !== null
        ? templates.find((t) => t.id === mode.tplId) ?? null
        : null;

  function selectView(id: number) {
    setMode({ kind: "view", tplId: id });
  }

  function startEdit(tpl: TemplateRead) {
    setMode({ kind: "edit", tpl });
  }

  function startCreate() {
    setMode({ kind: "create" });
  }

  // ---- Mutaciones ----

  function saveNew(values: TemplateFormValues) {
    startTransition(async () => {
      try {
        const created = await api.post<TemplateRead>("/api/v1/templates", values);
        toast.success(`Plantilla "${created.name}" creada`);
        setMode({ kind: "view", tplId: created.id });
        router.refresh();
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Error al crear");
      }
    });
  }

  function saveEdit(tplId: number, values: TemplateFormValues) {
    startTransition(async () => {
      try {
        // PATCH no acepta `name` (decisión backend); enviamos solo los
        // 3 campos editables.
        const updated = await api.patch<TemplateRead>(
          `/api/v1/templates/${tplId}`,
          {
            subject_template: values.subject_template,
            body_template: values.body_template,
            language: values.language,
          },
        );
        toast.success(`Plantilla "${updated.name}" guardada`);
        setMode({ kind: "view", tplId: updated.id });
        router.refresh();
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Error al guardar");
      }
    });
  }

  function deleteTpl(tpl: TemplateRead) {
    const confirmed = window.confirm(
      `Borrar plantilla "${tpl.name}"? Las sequences ya generadas no se ven afectadas (snapshot en steps_json); solo afecta a drafts futuros que pidan esta plantilla por nombre.`,
    );
    if (!confirmed) return;
    startTransition(async () => {
      try {
        await api.delete(`/api/v1/templates/${tpl.id}`);
        toast.success(`Plantilla "${tpl.name}" borrada`);
        setMode({ kind: "view", tplId: null });
        router.refresh();
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Error al borrar");
      }
    });
  }

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-[280px_1fr]">
      {/* Lista master */}
      <aside className="space-y-2">
        <header className="flex items-baseline justify-between">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            Plantillas ({templates.length})
          </h2>
          <button
            type="button"
            onClick={startCreate}
            disabled={pending}
            className="rounded-sm border border-wcm-accent/50 px-2 py-0.5 text-[11px] text-wcm-accent hover:border-wcm-accent hover:bg-wcm-accent/10 disabled:opacity-50"
          >
            + Crear
          </button>
        </header>
        <ul className="space-y-1">
          {templates.map((t) => {
            const active =
              mode.kind === "view" && mode.tplId === t.id ||
              (mode.kind === "edit" && mode.tpl.id === t.id);
            return (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() => selectView(t.id)}
                  disabled={pending}
                  className={cn(
                    "block w-full rounded-sm border px-3 py-2 text-left text-xs transition-colors disabled:opacity-50",
                    active
                      ? "border-wcm-accent/50 bg-wcm-accent/[0.08] text-wcm-text"
                      : "border-wcm-detail/40 bg-wcm-secondary/30 hover:border-muted-foreground",
                  )}
                >
                  <div className="font-semibold">
                    {t.name}
                  </div>
                  <div className="mt-0.5 text-[10.5px] text-muted-foreground">
                    {t.language} · {formatRelativeTime(t.updated_at)}
                  </div>
                </button>
              </li>
            );
          })}
          {templates.length === 0 && (
            <li className="rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-3 text-xs text-muted-foreground">
              Sin plantillas. Pulsa <strong>+ Crear</strong> para añadir
              la primera.
            </li>
          )}
        </ul>
      </aside>

      {/* Detalle / form */}
      <section>
        {mode.kind === "create" && (
          <TemplateForm
            mode="create"
            onSave={saveNew}
            onCancel={() => setMode({ kind: "view", tplId: null })}
            pending={pending}
          />
        )}

        {mode.kind === "edit" && (
          <TemplateForm
            mode="edit"
            initial={{
              name: mode.tpl.name,
              subject_template: mode.tpl.subject_template,
              body_template: mode.tpl.body_template,
              language: mode.tpl.language,
            }}
            onSave={(v) => saveEdit(mode.tpl.id, v)}
            onCancel={() =>
              setMode({ kind: "view", tplId: mode.tpl.id })
            }
            pending={pending}
          />
        )}

        {mode.kind === "view" && selectedTpl && (
          <TemplateView
            tpl={selectedTpl}
            onEdit={() => startEdit(selectedTpl)}
            onDelete={() => deleteTpl(selectedTpl)}
            pending={pending}
          />
        )}

        {mode.kind === "view" && !selectedTpl && (
          <div className="rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-6 text-center text-xs text-muted-foreground">
            Selecciona una plantilla a la izquierda o pulsa{" "}
            <strong>+ Crear</strong> para añadir una.
          </div>
        )}
      </section>
    </div>
  );
}

// ---------- TemplateView ----------

function TemplateView({
  tpl,
  onEdit,
  onDelete,
  pending,
}: {
  tpl: TemplateRead;
  onEdit: () => void;
  onDelete: () => void;
  pending: boolean;
}) {
  return (
    <article className="space-y-4 rounded-sm border border-wcm-detail/40 bg-wcm-secondary/30 p-4 text-xs">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-wcm-text">{tpl.name}</h3>
          <div className="mt-0.5 text-[11px] text-muted-foreground">
            <code className="text-wcm-text/80">{tpl.language}</code>
            <span className="mx-1.5">·</span>
            actualizada {formatRelativeTime(tpl.updated_at)}
          </div>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onEdit}
            disabled={pending}
            className="rounded-sm border border-wcm-detail/60 px-2.5 py-1 text-[11px] text-wcm-text hover:border-wcm-accent hover:text-wcm-accent disabled:opacity-50"
          >
            Editar
          </button>
          <button
            type="button"
            onClick={onDelete}
            disabled={pending}
            className="rounded-sm border border-wcm-detail/60 px-2.5 py-1 text-[11px] text-wcm-danger hover:border-wcm-danger disabled:opacity-50"
          >
            Borrar
          </button>
        </div>
      </header>

      <div>
        <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
          Asunto (Jinja2)
        </div>
        <pre className="mt-1 whitespace-pre-wrap break-words rounded-sm border border-wcm-detail/30 bg-wcm-primary p-2 font-mono text-[11px] text-wcm-text">
          {tpl.subject_template}
        </pre>
      </div>

      <div>
        <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
          Cuerpo (Jinja2)
        </div>
        <pre className="mt-1 whitespace-pre-wrap break-words rounded-sm border border-wcm-detail/30 bg-wcm-primary p-2 font-mono text-[11px] text-wcm-text">
          {tpl.body_template}
        </pre>
      </div>

      <JinjaHelp />
    </article>
  );
}

// ---------- TemplateForm ----------

interface TemplateFormValues {
  name: string;
  subject_template: string;
  body_template: string;
  language: string;
}

function TemplateForm({
  mode,
  initial,
  onSave,
  onCancel,
  pending,
}: {
  mode: "create" | "edit";
  initial?: TemplateFormValues;
  onSave: (values: TemplateFormValues) => void;
  onCancel: () => void;
  pending: boolean;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [subject, setSubject] = useState(initial?.subject_template ?? "");
  const [body, setBody] = useState(initial?.body_template ?? "");
  const [language, setLanguage] = useState(initial?.language ?? "es");

  const isEdit = mode === "edit";
  const canSave =
    !pending &&
    name.trim() !== "" &&
    subject.trim() !== "" &&
    body.trim() !== "";

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSave) return;
    onSave({
      name: name.trim(),
      subject_template: subject,
      body_template: body,
      language,
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-sm border border-wcm-accent/30 bg-wcm-secondary/30 p-4 text-xs"
    >
      <header className="text-[10.5px] uppercase tracking-wider text-wcm-accent">
        {isEdit ? "Editando plantilla" : "Nueva plantilla"}
      </header>

      <Field htmlFor="tpl-name" label="Nombre (clave única)">
        <input
          id="tpl-name"
          type="text"
          maxLength={80}
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={pending || isEdit}
          title={
            isEdit
              ? "No editable — renombrar rompería sequences históricas"
              : undefined
          }
          placeholder="bar_intro_es"
          className={inputClass}
        />
        {!isEdit && (
          <p className="mt-1 text-[10px] text-muted-foreground">
            Identificador opaco que el composer usa para resolver la
            plantilla. Snake_case, sin espacios. Una vez creado NO se
            puede renombrar.
          </p>
        )}
      </Field>

      <Field htmlFor="tpl-language" label="Idioma">
        <select
          id="tpl-language"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          disabled={pending}
          className={cn(inputClass, "w-24")}
        >
          <option value="es">es</option>
          <option value="en">en</option>
          <option value="pt">pt</option>
          <option value="fr">fr</option>
        </select>
      </Field>

      <Field htmlFor="tpl-subject" label="Asunto (Jinja2)">
        <input
          id="tpl-subject"
          type="text"
          required
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          disabled={pending}
          placeholder="{{ business_name }}, una idea sobre vuestra web"
          className={inputClass}
        />
      </Field>

      <Field htmlFor="tpl-body" label="Cuerpo (Jinja2)">
        <textarea
          id="tpl-body"
          rows={16}
          required
          value={body}
          onChange={(e) => setBody(e.target.value)}
          disabled={pending}
          placeholder="Hola {{ business_name }},&#10;&#10;Te escribo desde {{ company_name }}..."
          className="w-full resize-y rounded-sm border border-wcm-detail/70 bg-wcm-primary p-2 font-mono text-[11.5px] text-wcm-text placeholder:text-muted-foreground focus:border-wcm-accent focus:outline-none disabled:opacity-50"
        />
      </Field>

      <JinjaHelp />

      <div className="flex justify-end gap-2 pt-1">
        <button
          type="button"
          onClick={onCancel}
          disabled={pending}
          className="rounded-sm border border-wcm-detail/60 px-3 py-1 text-xs text-wcm-text/80 hover:border-wcm-detail hover:text-wcm-text disabled:opacity-50"
        >
          Cancelar
        </button>
        <button
          type="submit"
          disabled={!canSave}
          className="rounded-sm bg-wcm-accent px-3 py-1 text-xs font-semibold text-wcm-primary transition-colors hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {pending ? "Guardando…" : isEdit ? "Guardar →" : "Crear plantilla →"}
        </button>
      </div>
    </form>
  );
}

function JinjaHelp() {
  return (
    <details className="rounded-sm border border-wcm-detail/30 bg-wcm-primary p-2 text-[11px]">
      <summary className="cursor-pointer text-muted-foreground hover:text-wcm-text">
        Variables Jinja2 disponibles
      </summary>
      <div className="mt-2 grid grid-cols-1 gap-1 text-[10.5px] text-wcm-text/80 sm:grid-cols-2">
        <code>{"{{ business_name }}"}</code>
        <code>{"{{ website_url }}"}</code>
        <code>{"{{ builder_label }}"}</code>
        <code>{"{{ sender_name }}"}</code>
        <code>{"{{ company_name }}"}</code>
        <code>{"{{ company_city }}"}</code>
        <code>{"{{ company_contact_email }}"}</code>
        <code>{"{{ legal_block }}"}</code>
        <code>{"{{ opt_out_url }}"}</code>
        <code>{"{{ previous_subject }}"}</code>
      </div>
      <p className="mt-2 text-[10.5px] text-muted-foreground">
        El composer valida que cada paso renderizado incluya{" "}
        <code>{"{{ company_name }}"}</code>, CIF, dirección y{" "}
        <code>{"{{ opt_out_url }}"}</code>. Si los omites en el body,
        los drafts generados quedarán como NO aprobables.
      </p>
    </details>
  );
}

const inputClass =
  "h-8 w-full rounded-sm border border-wcm-detail/70 bg-wcm-primary px-2 text-xs text-wcm-text placeholder:text-muted-foreground focus:border-wcm-accent focus:outline-none disabled:opacity-50";

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
