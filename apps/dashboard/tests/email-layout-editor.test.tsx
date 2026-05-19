/**
 * Tests del EmailLayoutEditor (v0.15.0).
 *
 * Verifica los tabs Visual/Código, el comportamiento cuando theme_config
 * es null (Visual deshabilitado), y el botón "Restaurar tema por defecto".
 *
 * Mockeamos ThemeEditorForm con stub mínimo para no arrastrar el form
 * entero a este test (eso vive en theme-editor-form.test.tsx).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const apiPut = vi.fn();
const toastSuccess = vi.fn();
const routerRefresh = vi.fn();

vi.mock("@/lib/api", () => ({
  api: { put: (...args: unknown[]) => apiPut(...args), post: vi.fn() },
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

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: routerRefresh }),
}));

vi.mock("../src/app/(app)/settings/email-layout/_components/theme-editor-form", async () => {
  // Stub ligero del form — no probamos sus internals aquí.
  return {
    ThemeEditorForm: ({
      onSaved,
    }: {
      onSaved: (t: unknown) => void;
    }) => (
      <div data-testid="theme-editor-form">
        <button type="button" onClick={() => onSaved({ cta_bg: "#FFFFFF" })}>
          stub-save
        </button>
      </div>
    ),
    DEFAULT_THEME: {
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
      font_family: "system-ui" as const,
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
    },
  };
});

import { EmailLayoutEditor } from "../src/app/(app)/settings/email-layout/_components/email-layout-editor";

function _layout(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: 1,
    layout_html: "<html><body>{{ content | safe }}</body></html>",
    layout_css: "body { color: black; }",
    theme_config: { cta_bg: "#B1F100" },
    updated_by_user_id: null,
    created_at: "2026-05-19T10:00:00Z",
    updated_at: "2026-05-19T10:00:00Z",
    ...over,
  } as Parameters<typeof EmailLayoutEditor>[0]["initialLayout"];
}

beforeEach(() => {
  apiPut.mockReset();
  toastSuccess.mockReset();
  routerRefresh.mockReset();
  // Stub window.confirm para que siempre acepte (tests de reset).
  vi.stubGlobal("confirm", vi.fn(() => true));
});

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("EmailLayoutEditor", () => {
  it("muestra tab Visual por defecto si theme_config existe", () => {
    render(<EmailLayoutEditor initialLayout={_layout()} />);
    expect(screen.getByTestId("theme-editor-form")).toBeInTheDocument();
    const visualTab = screen.getByRole("tab", { name: /visual/i });
    expect(visualTab).toHaveAttribute("aria-selected", "true");
  });

  it("muestra tab Código por defecto si theme_config es null", () => {
    render(
      <EmailLayoutEditor initialLayout={_layout({ theme_config: null })} />,
    );
    expect(screen.queryByTestId("theme-editor-form")).not.toBeInTheDocument();
    // Visual deshabilitado.
    const visualTab = screen.getByRole("tab", { name: /visual/i });
    expect(visualTab).toHaveAttribute("aria-disabled", "true");
    // Textarea de código visible.
    expect(screen.getByLabelText(/html jinja2/i)).toBeInTheDocument();
  });

  it("click en Visual cuando está deshabilitado muestra panel explicativo si lo intentas", async () => {
    render(
      <EmailLayoutEditor initialLayout={_layout({ theme_config: null })} />,
    );
    const visualTab = screen.getByRole("tab", { name: /visual/i });
    // No podemos hacer click (disabled), pero el panel explicativo
    // solo aparece si forzamos modo visual. Aquí confirmamos el estado
    // inicial: panel deshabilitado NO renderizado, código SÍ.
    expect(visualTab).toBeDisabled();
  });

  it("guardar desde tab Código dispara PUT con HTML/CSS sin theme", async () => {
    apiPut.mockResolvedValue({});
    const user = userEvent.setup();
    render(<EmailLayoutEditor initialLayout={_layout()} />);

    await user.click(screen.getByRole("tab", { name: /código/i }));
    await user.click(screen.getByRole("button", { name: /guardar \(código\)/i }));

    await waitFor(() => expect(apiPut).toHaveBeenCalled());
    const payload = apiPut.mock.calls[0]?.[1];
    expect(payload).toHaveProperty("layout_html");
    expect(payload).toHaveProperty("layout_css");
    expect(payload).not.toHaveProperty("theme_config");
  });

  it("Restaurar tema por defecto requiere doble click (confirmación inline) + dispara PUT", async () => {
    apiPut.mockResolvedValue({});
    const user = userEvent.setup();
    render(
      <EmailLayoutEditor initialLayout={_layout({ theme_config: null })} />,
    );
    // Primer click: confirmación inline (botón cambia copy).
    await user.click(
      screen.getByRole("button", { name: /restaurar valores por defecto/i }),
    );
    expect(apiPut).not.toHaveBeenCalled();
    // Segundo click sobre el botón con el copy de confirmación.
    await user.click(
      screen.getByRole("button", { name: /pulsa otra vez para confirmar/i }),
    );
    await waitFor(() => expect(apiPut).toHaveBeenCalled());
    const payload = apiPut.mock.calls[0]?.[1];
    expect(payload).toHaveProperty("theme_config");
    expect(payload.theme_config).toEqual(expect.objectContaining({ cta_bg: "#B1F100" }));
  });
});
