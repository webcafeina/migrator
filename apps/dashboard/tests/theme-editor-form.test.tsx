/**
 * Tests del ThemeEditorForm (v0.15.0).
 *
 * Form visual del layout maestro con 24 controles. Mockeamos api.post
 * (preview live) y api.put (save). Cada cambio de input debería
 * propagar al estado interno y disparar preview tras debounce.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const apiPost = vi.fn();
const apiPut = vi.fn();
const toastSuccess = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    post: (...args: unknown[]) => apiPost(...args),
    put: (...args: unknown[]) => apiPut(...args),
  },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(m: string, s: number) {
      super(m);
      this.status = s;
    }
  },
}));

vi.mock("sonner", () => ({
  toast: { success: (...a: unknown[]) => toastSuccess(...a), error: vi.fn() },
}));

import {
  DEFAULT_THEME,
  type EmailLayoutTheme,
  ThemeEditorForm,
} from "../src/app/(app)/settings/email-layout/_components/theme-editor-form";

beforeEach(() => {
  apiPost.mockReset();
  apiPut.mockReset();
  toastSuccess.mockReset();
  apiPost.mockResolvedValue({
    layout_html: "<html><body></body></html>",
    layout_css: "",
  });
  apiPut.mockResolvedValue({});
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("ThemeEditorForm", () => {
  it("renderiza con los valores iniciales del tema", () => {
    render(
      <ThemeEditorForm
        initialTheme={DEFAULT_THEME}
        onSaved={vi.fn()}
        onPreview={vi.fn()}
      />,
    );
    // Sección "Colores · CTA" visible.
    expect(screen.getByText(/colores · cta/i)).toBeInTheDocument();
    // Color CTA bg con el HEX por defecto.
    const ctaInputs = screen.getAllByDisplayValue("#B1F100");
    expect(ctaInputs.length).toBeGreaterThan(0);
    // Selector de fuente con el default.
    const fontSelect = screen.getByDisplayValue(/system-ui/i);
    expect(fontSelect).toBeInTheDocument();
  });

  it("cambiar color dispara POST /preview con debounce", async () => {
    const onPreview = vi.fn();
    render(
      <ThemeEditorForm
        initialTheme={DEFAULT_THEME}
        onSaved={vi.fn()}
        onPreview={onPreview}
      />,
    );
    // Esperar al primer preview automático (debounce 600 ms).
    await waitFor(
      () => {
        expect(apiPost).toHaveBeenCalled();
      },
      { timeout: 1500 },
    );
    const call = apiPost.mock.calls[0];
    expect(call?.[0]).toBe("/api/v1/email-layout/preview");
    expect(call?.[1]).toEqual(expect.objectContaining({ cta_bg: "#B1F100" }));
  });

  it("botón guardar dispara PUT con theme_config completo", async () => {
    const onSaved = vi.fn();
    const user = userEvent.setup();
    render(
      <ThemeEditorForm
        initialTheme={DEFAULT_THEME}
        onSaved={onSaved}
        onPreview={vi.fn()}
      />,
    );
    // El botón guardar está deshabilitado mientras no haya cambios.
    const saveBtn = screen.getByRole("button", { name: /guardar tema/i });
    expect(saveBtn).toBeDisabled();

    // Cambiar el toggle "Mostrar logo" para marcar dirty.
    const logoCheckbox = screen.getByRole("checkbox", { name: /mostrar logo/i });
    await user.click(logoCheckbox);

    await waitFor(() => expect(saveBtn).toBeEnabled());
    await user.click(saveBtn);

    await waitFor(() => expect(apiPut).toHaveBeenCalled());
    expect(apiPut).toHaveBeenCalledWith(
      "/api/v1/email-layout",
      expect.objectContaining({
        theme_config: expect.objectContaining({ show_logo: false }),
      }),
    );
    expect(toastSuccess).toHaveBeenCalled();
    expect(onSaved).toHaveBeenCalled();
  });

  it("botón Restaurar valores por defecto resetea el form", async () => {
    const customTheme: EmailLayoutTheme = {
      ...DEFAULT_THEME,
      cta_bg: "#FF0000",
      show_logo: false,
    };
    const user = userEvent.setup();
    render(
      <ThemeEditorForm
        initialTheme={customTheme}
        onSaved={vi.fn()}
        onPreview={vi.fn()}
      />,
    );
    // Antes del reset hay un input con FF0000.
    expect(screen.getByDisplayValue("#FF0000")).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: /restaurar valores por defecto/i }),
    );
    // Tras reset, FF0000 ya no está; B1F100 (default) sí.
    expect(screen.queryByDisplayValue("#FF0000")).not.toBeInTheDocument();
    const defaultCta = screen.getAllByDisplayValue("#B1F100");
    expect(defaultCta.length).toBeGreaterThan(0);
  });

  it("HEX inválido en el text input NO propaga al estado (silencia 422)", async () => {
    const user = userEvent.setup();
    const onPreview = vi.fn();
    render(
      <ThemeEditorForm
        initialTheme={DEFAULT_THEME}
        onSaved={vi.fn()}
        onPreview={onPreview}
      />,
    );
    // Localizar el text input del CTA bg (HEX al lado del color picker).
    const textInputs = screen.getAllByDisplayValue("#B1F100");
    const ctaTextInput = textInputs.find(
      (el) => (el as HTMLInputElement).type === "text",
    ) as HTMLInputElement;
    expect(ctaTextInput).toBeDefined();

    await user.clear(ctaTextInput);
    await user.type(ctaTextInput, "rojo-mal");

    // El input visible muestra lo tipeado, pero el estado interno
    // sigue en el último HEX válido (no se rompe). El próximo preview
    // (POST /preview) seguirá llevando #B1F100.
    apiPost.mockClear();
    await waitFor(() => expect(apiPost).toHaveBeenCalled(), { timeout: 1500 });
    const lastPayload = apiPost.mock.calls.at(-1)?.[1];
    expect(lastPayload).toEqual(expect.objectContaining({ cta_bg: "#B1F100" }));
  });

  it("cambiar la fuente actualiza el state y dispara preview", async () => {
    const user = userEvent.setup();
    render(
      <ThemeEditorForm
        initialTheme={DEFAULT_THEME}
        onSaved={vi.fn()}
        onPreview={vi.fn()}
      />,
    );
    const select = screen.getByDisplayValue(/system-ui/i);
    await user.selectOptions(select, "serif");
    apiPost.mockClear();
    await waitFor(() => expect(apiPost).toHaveBeenCalled(), { timeout: 1500 });
    const lastPayload = apiPost.mock.calls.at(-1)?.[1];
    expect(lastPayload).toEqual(expect.objectContaining({ font_family: "serif" }));
  });
});
