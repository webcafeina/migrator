"use client";

import { useState } from "react";

import { EmailPreviewIframe } from "@/components/email-preview-iframe";
import { RichTextEditor } from "@/components/rich-text-editor";
import { TestSendDialog } from "@/components/test-send-dialog";
import { cn } from "@/lib/utils";

export interface EditableStep {
  step_index: number;
  subject: string | null;
  body: string;
  delay_days_from_previous: number;
}

interface SequenceStepEditorProps {
  initialStep: EditableStep;
  /** ID de la sequence al que pertenece el paso. Necesario para
   *  enrutar los endpoints de preview y test-send (que viven bajo
   *  `/sequences/{id}/steps/{idx}/...`). */
  sequenceId: number;
  /** Llamado con el step editado al pulsar Guardar. El padre se
   *  encarga del PATCH (necesita los demás pasos para enviar la lista
   *  completa). */
  onSave: (step: EditableStep) => void;
  onCancel: () => void;
  pending?: boolean;
}

/**
 * Form inline para editar un paso de una secuencia de contacto.
 * Subject + body HTML (Tiptap) + delay_days_from_previous. NO añade/
 * elimina pasos (decisión v0.12.0 — mantiene la estructura del template
 * original).
 *
 * v0.14.0: el body es HTML editado con WYSIWYG. Tiptap acepta texto
 * plano legacy y lo envuelve auto en `<p>` al hidratar. Botones
 * adicionales:
 * - "Vista previa" → expande iframe con el HTML final renderizado
 *   (layout maestro + premailer aplicados, lo que llegará al lead).
 * - "Enviar prueba" → modal con input email + envío real vía Resend.
 */
export function SequenceStepEditor({
  initialStep,
  sequenceId,
  onSave,
  onCancel,
  pending = false,
}: SequenceStepEditorProps) {
  const [subject, setSubject] = useState(initialStep.subject ?? "");
  const [body, setBody] = useState(initialStep.body);
  const [delay, setDelay] = useState(initialStep.delay_days_from_previous);
  const [showPreview, setShowPreview] = useState(false);
  const [testSendOpen, setTestSendOpen] = useState(false);

  function handleSave() {
    onSave({
      step_index: initialStep.step_index,
      subject: subject.trim() === "" ? null : subject,
      body,
      delay_days_from_previous: Math.max(0, Math.floor(delay)),
    });
  }

  return (
    <>
      <div className="space-y-3 rounded-sm border border-wcm-accent/40 bg-wcm-secondary/30 p-3 text-xs">
        <div className="flex items-baseline justify-between text-[10.5px] uppercase tracking-wider text-wcm-accent">
          <span>Editando paso {initialStep.step_index + 1}</span>
          <span className="text-muted-foreground">
            Guardar re-valida footer legal
          </span>
        </div>

        <Field htmlFor={`step-${initialStep.step_index}-subject`} label="Asunto">
          <input
            id={`step-${initialStep.step_index}-subject`}
            type="text"
            maxLength={255}
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            disabled={pending}
            className={inputClass}
          />
        </Field>

        <Field htmlFor={`step-${initialStep.step_index}-body`} label="Cuerpo">
          <RichTextEditor
            initialHtml={body}
            onChange={setBody}
            disabled={pending}
          />
          <p className="mt-1 text-[10px] text-muted-foreground">
            Mantén la firma legal del pie y el enlace de opt-out
            (<code>https://…/opt-out?token=…</code>) intactos o la
            re-validación marcará el draft como NO aprobable.
          </p>
        </Field>

        <Field
          htmlFor={`step-${initialStep.step_index}-delay`}
          label="Retraso desde paso anterior (días)"
        >
          <input
            id={`step-${initialStep.step_index}-delay`}
            type="number"
            min={0}
            max={90}
            value={delay}
            onChange={(e) => setDelay(Number(e.target.value))}
            disabled={pending}
            className={cn(inputClass, "w-24 tabular-nums")}
          />
        </Field>

        <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setShowPreview((v) => !v)}
              disabled={pending}
              className="rounded-sm border border-wcm-detail/60 px-3 py-1 text-xs text-wcm-text/80 transition-colors hover:border-wcm-detail hover:text-wcm-text disabled:opacity-50"
            >
              {showPreview ? "Ocultar vista previa" : "Vista previa →"}
            </button>
            <button
              type="button"
              onClick={() => setTestSendOpen(true)}
              disabled={pending}
              className="rounded-sm border border-wcm-detail/60 px-3 py-1 text-xs text-wcm-text/80 transition-colors hover:border-wcm-detail hover:text-wcm-text disabled:opacity-50"
            >
              Enviar prueba →
            </button>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onCancel}
              disabled={pending}
              className="rounded-sm border border-wcm-detail/60 px-3 py-1 text-xs text-wcm-text/80 transition-colors hover:border-wcm-detail hover:text-wcm-text disabled:opacity-50"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={pending || body.replace(/<[^>]+>/g, "").trim() === ""}
              className="rounded-sm bg-wcm-accent px-3 py-1 text-xs font-semibold text-wcm-primary transition-colors hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {pending ? "Guardando…" : "Guardar paso →"}
            </button>
          </div>
        </div>

        {showPreview && (
          <div className="pt-2">
            <EmailPreviewIframe
              fetchUrl={`/api/v1/outreach/sequences/${sequenceId}/steps/${initialStep.step_index}/preview`}
              ariaLabel={`Vista previa del paso ${initialStep.step_index + 1}`}
              height={520}
            />
            <p className="mt-1 text-[10px] text-muted-foreground">
              Preview del snapshot persistido. Guarda los cambios y vuelve
              a abrir para ver el HTML con tus ediciones.
            </p>
          </div>
        )}
      </div>

      <TestSendDialog
        sequenceId={sequenceId}
        stepIndex={initialStep.step_index}
        open={testSendOpen}
        onClose={() => setTestSendOpen(false)}
      />
    </>
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
