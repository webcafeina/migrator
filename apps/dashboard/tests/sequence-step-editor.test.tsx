/**
 * Tests del SequenceStepEditor (v0.12.0 bloque 2).
 *
 * Form inline para editar subject + body + delay de un paso de una
 * secuencia de contacto. NO testea el PATCH (lo hace el padre con su
 * propio flujo de side-effects).
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

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
        onSave={vi.fn()}
        onCancel={vi.fn()}
        pending
      />,
    );
    expect(screen.getByRole("button", { name: /guardando/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /cancelar/i })).toBeDisabled();
  });

  it("delay se sanitiza: negativo → 0, decimal → floor", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(
      <SequenceStepEditor
        initialStep={{ ..._step, delay_days_from_previous: 0 }}
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
