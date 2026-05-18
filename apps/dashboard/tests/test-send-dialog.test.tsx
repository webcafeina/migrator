/**
 * Tests del TestSendDialog (v0.14.0).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const apiPost = vi.fn();
const toastSuccess = vi.fn();

vi.mock("@/lib/api", () => ({
  api: { post: (...args: unknown[]) => apiPost(...args) },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(m: string, s: number) {
      super(m);
      this.status = s;
    }
  },
}));

vi.mock("sonner", () => ({
  toast: { success: (...args: unknown[]) => toastSuccess(...args) },
}));

import { TestSendDialog } from "../src/components/test-send-dialog";

beforeEach(() => {
  apiPost.mockReset();
  toastSuccess.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("TestSendDialog", () => {
  it("no se renderiza cuando open=false", () => {
    render(
      <TestSendDialog
        sequenceId={1}
        stepIndex={0}
        open={false}
        onClose={vi.fn()}
      />,
    );
    expect(
      screen.queryByText(/enviar correo de prueba/i),
    ).not.toBeInTheDocument();
  });

  it("botón Enviar deshabilitado con email inválido", async () => {
    render(
      <TestSendDialog
        sequenceId={1}
        stepIndex={0}
        open
        onClose={vi.fn()}
        defaultTo="no-es-email"
      />,
    );
    expect(
      screen.getByRole("button", { name: /enviar prueba/i }),
    ).toBeDisabled();
  });

  it("happy path: POST al endpoint correcto + toast success", async () => {
    apiPost.mockResolvedValue({
      provider_message_id: "re_xyz",
      to: "test@webcafeina.com",
    });
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <TestSendDialog
        sequenceId={42}
        stepIndex={3}
        open
        onClose={onClose}
        defaultTo="test@webcafeina.com"
      />,
    );
    await user.click(screen.getByRole("button", { name: /enviar prueba/i }));
    await waitFor(() => expect(apiPost).toHaveBeenCalled());

    expect(apiPost).toHaveBeenCalledWith(
      "/api/v1/outreach/sequences/42/steps/3/test-send",
      { to: "test@webcafeina.com" },
    );
    expect(toastSuccess).toHaveBeenCalledWith(
      expect.stringContaining("test@webcafeina.com"),
      expect.objectContaining({ description: expect.stringContaining("re_xyz") }),
    );
    expect(onClose).toHaveBeenCalled();
  });

  it("error de API se muestra en el dialog sin cerrarlo", async () => {
    apiPost.mockRejectedValue(
      new (class extends Error {
        status = 502;
      })("Domain not verified"),
    );
    // Forzamos ApiError import path para que el chequeo `instanceof
    // ApiError` falle y caigamos al fallback `Error`.
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <TestSendDialog
        sequenceId={1}
        stepIndex={0}
        open
        onClose={onClose}
        defaultTo="test@webcafeina.com"
      />,
    );
    await user.click(screen.getByRole("button", { name: /enviar prueba/i }));
    await waitFor(() =>
      expect(
        screen.getByText(/Error al enviar prueba|Domain not verified/i),
      ).toBeInTheDocument(),
    );
    expect(onClose).not.toHaveBeenCalled();
  });

  it("Cancelar dispara onClose sin POST", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <TestSendDialog
        sequenceId={1}
        stepIndex={0}
        open
        onClose={onClose}
        defaultTo="test@webcafeina.com"
      />,
    );
    await user.click(screen.getByRole("button", { name: /cancelar/i }));
    expect(onClose).toHaveBeenCalled();
    expect(apiPost).not.toHaveBeenCalled();
  });
});
