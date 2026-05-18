/**
 * Tests del SequenceStepEditor (v0.12.0 bloque 2, refactor v0.14.0).
 *
 * Form inline para editar subject + body HTML (Tiptap) + delay de un
 * paso de una secuencia de contacto. v0.14.0: añadidos botones
 * "Vista previa" y "Enviar prueba".
 *
 * Estrategia: mockeamos `RichTextEditor` como un <textarea> simple
 * para no arrastrar Tiptap a JSDOM (necesita contentEditable que
 * happy-dom no soporta bien). Mockeamos también `EmailPreviewIframe`
 * y `TestSendDialog` con stubs visuales que no fetchan ni renderizan
 * iframes.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/components/rich-text-editor", () => ({
  RichTextEditor: ({
    initialHtml,
    onChange,
    disabled,
  }: {
    initialHtml: string;
    onChange: (v: string) => void;
    disabled?: boolean;
  }) => (
    <textarea
      aria-label="Cuerpo"
      defaultValue={initialHtml}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
    />
  ),
}));

vi.mock("@/components/email-preview-iframe", () => ({
  EmailPreviewIframe: ({ fetchUrl }: { fetchUrl: string }) => (
    <div data-testid="preview-iframe" data-url={fetchUrl}>
      preview
    </div>
  ),
}));

vi.mock("@/components/test-send-dialog", () => ({
  TestSendDialog: ({ open }: { open: boolean }) =>
    open ? <div data-testid="test-send-dialog">test send dialog</div> : null,
}));

import {
  type EditableStep,
  SequenceStepEditor,
} from "../src/app/(app)/leads/_components/sequence-step-editor";

const _step: EditableStep = {
  step_index: 0,
  subject: "Asunto original",
  body: "Cuerpo original\ncon múltiples líneas",
  delay_days_from_previous: 0,
};

afterEach(() => {
  vi.clearAllMocks();
});

describe("SequenceStepEditor", () => {
  it("renderiza inputs con los valores iniciales del paso", () => {
    render(
      <SequenceStepEditor
        initialStep={_step}
        sequenceId={42}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByLabelText(/asunto/i)).toHaveValue("Asunto original");
    expect(screen.getByLabelText(/cuerpo/i)).toHaveValue(
      "Cuerpo original\ncon múltiples líneas",
    );
    expect(screen.getByLabelText(/retraso desde paso anterior/i)).toHaveValue(0);
  });

  it("muestra el header con el número de paso correcto", () => {
    render(
      <SequenceStepEditor
        initialStep={{ ..._step, step_index: 1 }}
        sequenceId={42}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText(/editando paso 2/i)).toBeInTheDocument();
  });

  it("Cancelar dispara onCancel sin tocar el paso", async () => {
    const onCancel = vi.fn();
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(
      <SequenceStepEditor
        initialStep={_step}
        sequenceId={42}
        onSave={onSave}
        onCancel={onCancel}
      />,
    );
    await user.click(screen.getByRole("button", { name: /cancelar/i }));
    expect(onCancel).toHaveBeenCalledOnce();
    expect(onSave).not.toHaveBeenCalled();
  });

  it("Guardar dispara onSave con el step editado", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(
      <SequenceStepEditor
        initialStep={_step}
        sequenceId={42}
        onSave={onSave}
        onCancel={vi.fn()}
      />,
    );
    const subjectInput = screen.getByLabelText(/asunto/i);
    await user.clear(subjectInput);
    await user.type(subjectInput, "Nuevo asunto editado");

    const delayInput = screen.getByLabelText(/retraso desde paso anterior/i);
    await user.clear(delayInput);
    await user.type(delayInput, "5");

    await user.click(screen.getByRole("button", { name: /guardar paso/i }));

    expect(onSave).toHaveBeenCalledOnce();
    const saved = onSave.mock.calls[0]?.[0] as EditableStep;
    expect(saved.step_index).toBe(0);
    expect(saved.subject).toBe("Nuevo asunto editado");
    expect(saved.delay_days_from_previous).toBe(5);
  });

  it("subject vacío se envía como null (no string vacío)", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(
      <SequenceStepEditor
        initialStep={_step}
        sequenceId={42}
        onSave={onSave}
        onCancel={vi.fn()}
      />,
    );
    await user.clear(screen.getByLabelText(/asunto/i));
    await user.click(screen.getByRole("button", { name: /guardar paso/i }));
    const saved = onSave.mock.calls[0]?.[0] as EditableStep;
    expect(saved.subject).toBeNull();
  });

  it("botón Guardar deshabilitado con body vacío", async () => {
    const user = userEvent.setup();
    render(
      <SequenceStepEditor
        initialStep={_step}
        sequenceId={42}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    await user.clear(screen.getByLabelText(/cuerpo/i));
    expect(screen.getByRole("button", { name: /guardar paso/i })).toBeDisabled();
  });

  it("estado pending deshabilita ambos botones y muestra 'Guardando…'", () => {
    render(
      <SequenceStepEditor
        initialStep={_step}
        sequenceId={42}
        onSave={vi.fn()}
        onCancel={vi.fn()}
        pending
      />,
    );
    expect(screen.getByRole("button", { name: /guardando/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /cancelar/i })).toBeDisabled();
  });

  // --- v0.14.0: botones vista previa + enviar prueba ---

  it("botón Vista previa alterna el iframe colapsable", async () => {
    const user = userEvent.setup();
    render(
      <SequenceStepEditor
        initialStep={_step}
        sequenceId={77}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("preview-iframe")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /vista previa/i }));
    const iframe = screen.getByTestId("preview-iframe");
    expect(iframe).toHaveAttribute(
      "data-url",
      "/api/v1/outreach/sequences/77/steps/0/preview",
    );
    await user.click(screen.getByRole("button", { name: /ocultar vista previa/i }));
    expect(screen.queryByTestId("preview-iframe")).not.toBeInTheDocument();
  });

  it("botón Enviar prueba abre el TestSendDialog", async () => {
    const user = userEvent.setup();
    render(
      <SequenceStepEditor
        initialStep={_step}
        sequenceId={77}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("test-send-dialog")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /enviar prueba/i }));
    expect(screen.getByTestId("test-send-dialog")).toBeInTheDocument();
  });

  it("delay se sanitiza: negativo → 0, decimal → floor", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(
      <SequenceStepEditor
        initialStep={{ ..._step, delay_days_from_previous: 0 }}
        sequenceId={42}
        onSave={onSave}
        onCancel={vi.fn()}
      />,
    );
    const delayInput = screen.getByLabelText(/retraso desde paso anterior/i);
    await user.clear(delayInput);
    await user.type(delayInput, "3");
    await user.click(screen.getByRole("button", { name: /guardar paso/i }));
    const saved = onSave.mock.calls[0]?.[0] as EditableStep;
    expect(saved.delay_days_from_previous).toBe(3);
  });
});
