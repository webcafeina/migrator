/**
 * Tests del LeadDeleteDialog (v0.12.0 bloque 3).
 *
 * Modal de confirmación typing-to-confirm (patrón GitHub) para hard
 * delete de un lead.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const apiDelete = vi.fn();

vi.mock("@/lib/api", () => ({
  api: { delete: (...args: unknown[]) => apiDelete(...args) },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
}));

import { LeadDeleteDialog } from "../src/app/(app)/leads/_components/lead-delete-dialog";

beforeEach(() => {
  apiDelete.mockReset();
});
afterEach(() => {
  vi.clearAllMocks();
});

describe("LeadDeleteDialog", () => {
  it("no se renderiza cuando open=false", () => {
    render(
      <LeadDeleteDialog
        leadId={1}
        confirmationText="Bar Pepe"
        open={false}
        onClose={vi.fn()}
        onDeleted={vi.fn()}
      />,
    );
    expect(
      screen.queryByText(/borrar lead permanentemente/i),
    ).not.toBeInTheDocument();
  });

  it("muestra el título + warning + texto a tipear cuando open=true", () => {
    render(
      <LeadDeleteDialog
        leadId={1}
        confirmationText="Bar Pepe"
        open
        onClose={vi.fn()}
        onDeleted={vi.fn()}
      />,
    );
    expect(
      screen.getByText(/borrar lead permanentemente/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/no se puede deshacer/i)).toBeInTheDocument();
    expect(screen.getByText("Bar Pepe")).toBeInTheDocument();
  });

  it("botón Borrar deshabilitado hasta tipear el texto exacto", async () => {
    const user = userEvent.setup();
    render(
      <LeadDeleteDialog
        leadId={1}
        confirmationText="Bar Pepe"
        open
        onClose={vi.fn()}
        onDeleted={vi.fn()}
      />,
    );
    const btn = screen.getByRole("button", { name: /borrar permanentemente/i });
    expect(btn).toBeDisabled();

    const input = screen.getByLabelText(/para confirmar, escribe/i);
    await user.type(input, "Bar Pep");
    expect(btn).toBeDisabled();

    await user.type(input, "e");
    expect(btn).toBeEnabled();
  });

  it("typing case-sensitive: 'bar pepe' != 'Bar Pepe'", async () => {
    const user = userEvent.setup();
    render(
      <LeadDeleteDialog
        leadId={1}
        confirmationText="Bar Pepe"
        open
        onClose={vi.fn()}
        onDeleted={vi.fn()}
      />,
    );
    await user.type(
      screen.getByLabelText(/para confirmar, escribe/i),
      "bar pepe",
    );
    expect(
      screen.getByRole("button", { name: /borrar permanentemente/i }),
    ).toBeDisabled();
  });

  it("click Borrar dispara DELETE y onDeleted al éxito", async () => {
    apiDelete.mockResolvedValue(undefined);
    const onDeleted = vi.fn();
    const user = userEvent.setup();
    render(
      <LeadDeleteDialog
        leadId={42}
        confirmationText="Bar Pepe"
        open
        onClose={vi.fn()}
        onDeleted={onDeleted}
      />,
    );
    await user.type(
      screen.getByLabelText(/para confirmar, escribe/i),
      "Bar Pepe",
    );
    await user.click(
      screen.getByRole("button", { name: /borrar permanentemente/i }),
    );
    expect(apiDelete).toHaveBeenCalledWith("/api/v1/leads/42");
    // onDeleted llamado tras éxito (con startTransition → microtask).
    await vi.waitFor(() => expect(onDeleted).toHaveBeenCalled());
  });

  it("Cancelar dispara onClose sin tocar nada", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <LeadDeleteDialog
        leadId={1}
        confirmationText="Bar Pepe"
        open
        onClose={onClose}
        onDeleted={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: /cancelar/i }));
    expect(onClose).toHaveBeenCalledOnce();
    expect(apiDelete).not.toHaveBeenCalled();
  });
});
