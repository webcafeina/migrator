/**
 * Tests del TemplateManager (v0.12.0 bloque 4).
 *
 * Pantalla CRUD de plantillas Jinja2. Master-detail con render por
 * modo (view/edit/create). No testea side-effects post-await (mismo
 * bug React 19 + happy-dom).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const apiPost = vi.fn();
const apiPatch = vi.fn();
const apiDelete = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    post: (...a: unknown[]) => apiPost(...a),
    patch: (...a: unknown[]) => apiPatch(...a),
    delete: (...a: unknown[]) => apiDelete(...a),
  },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(m: string, s: number) {
      super(m);
      this.status = s;
    }
  },
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn(), replace: vi.fn() }),
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

import { TemplateManager } from "../src/app/(app)/settings/templates/_components/template-manager";

function _tpl(over: Record<string, unknown> = {}) {
  return {
    id: 1,
    name: "wix_intro_es",
    subject_template: "{{ business_name }}, una idea",
    body_template: "Hola...",
    language: "es",
    created_at: "2026-05-18T10:00:00Z",
    updated_at: "2026-05-18T10:00:00Z",
    ...over,
  };
}

beforeEach(() => {
  apiPost.mockReset();
  apiPatch.mockReset();
  apiDelete.mockReset();
});
afterEach(() => {
  vi.clearAllMocks();
});

describe("TemplateManager", () => {
  it("renderiza la lista de plantillas + empty state derecha", () => {
    render(
      <TemplateManager
        initialTemplates={[
          _tpl({ id: 1, name: "wix_intro_es" }),
          _tpl({ id: 2, name: "followup_es" }),
        ]}
      />,
    );
    expect(screen.getByText(/plantillas \(2\)/i)).toBeInTheDocument();
    expect(screen.getByText("wix_intro_es")).toBeInTheDocument();
    expect(screen.getByText("followup_es")).toBeInTheDocument();
    expect(screen.getByText(/selecciona una plantilla/i)).toBeInTheDocument();
  });

  it("empty state cuando no hay plantillas + sigue el botón Crear", () => {
    render(<TemplateManager initialTemplates={[]} />);
    expect(screen.getByText(/sin plantillas/i)).toBeInTheDocument();
    // 'Crear' visible (botón en cabecera).
    expect(
      screen.getByRole("button", { name: /\+ crear/i }),
    ).toBeVisible();
  });

  it("click en una plantilla muestra el detail con subject y body", async () => {
    const user = userEvent.setup();
    render(
      <TemplateManager
        initialTemplates={[
          _tpl({
            id: 5,
            name: "tpl_x",
            subject_template: "Asunto X",
            body_template: "Cuerpo X",
          }),
        ]}
      />,
    );
    await user.click(screen.getByRole("button", { name: /tpl_x/i }));
    expect(screen.getByText("Asunto X")).toBeInTheDocument();
    expect(screen.getByText("Cuerpo X")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^editar$/i })).toBeVisible();
  });

  it("click '+ Crear' muestra form con nombre editable", async () => {
    const user = userEvent.setup();
    render(<TemplateManager initialTemplates={[]} />);
    await user.click(screen.getByRole("button", { name: /\+ crear/i }));
    expect(screen.getByText(/nueva plantilla/i)).toBeInTheDocument();
    // input name habilitado y vacío
    const nameInput = screen.getByLabelText(/nombre.*clave/i);
    expect(nameInput).toBeEnabled();
    expect(nameInput).toHaveValue("");
  });

  it("click 'Editar' muestra form con name deshabilitado + valores precargados", async () => {
    const user = userEvent.setup();
    render(
      <TemplateManager
        initialTemplates={[_tpl({ id: 1, name: "wix_intro_es" })]}
      />,
    );
    await user.click(screen.getByRole("button", { name: /wix_intro_es/i }));
    await user.click(screen.getByRole("button", { name: /^editar$/i }));
    expect(screen.getByText(/editando plantilla/i)).toBeInTheDocument();
    const nameInput = screen.getByLabelText(/nombre.*clave/i);
    expect(nameInput).toBeDisabled();
    expect(nameInput).toHaveValue("wix_intro_es");
  });

  it("submit create llama POST con shape correcta", async () => {
    apiPost.mockResolvedValue(_tpl({ id: 99, name: "nuevo_es" }));
    const user = userEvent.setup();
    render(<TemplateManager initialTemplates={[]} />);
    await user.click(screen.getByRole("button", { name: /\+ crear/i }));
    await user.type(screen.getByLabelText(/nombre.*clave/i), "nuevo_es");
    // userEvent.type interpreta `{` como meta-key — uso texto plano
    // sin Jinja2 vars en el test (la lógica que importa es el shape
    // del POST, no los caracteres especiales).
    await user.type(
      screen.getByLabelText(/asunto.*jinja2/i),
      "Hola business",
    );
    await user.type(
      screen.getByLabelText(/cuerpo.*jinja2/i),
      "Cuerpo nuevo",
    );
    await user.click(
      screen.getByRole("button", { name: /crear plantilla/i }),
    );
    expect(apiPost).toHaveBeenCalledWith(
      "/api/v1/templates",
      expect.objectContaining({
        name: "nuevo_es",
        subject_template: "Hola business",
        body_template: "Cuerpo nuevo",
        language: "es",
      }),
    );
  });

  it("submit edit llama PATCH sin enviar name (campo no editable)", async () => {
    apiPatch.mockResolvedValue(_tpl({ id: 1, name: "wix_intro_es" }));
    const user = userEvent.setup();
    render(
      <TemplateManager
        initialTemplates={[_tpl({ id: 1, name: "wix_intro_es" })]}
      />,
    );
    await user.click(screen.getByRole("button", { name: /wix_intro_es/i }));
    await user.click(screen.getByRole("button", { name: /^editar$/i }));
    const subjectInput = screen.getByLabelText(/asunto.*jinja2/i);
    await user.clear(subjectInput);
    await user.type(subjectInput, "Nuevo asunto");
    await user.click(
      screen.getByRole("button", { name: /^guardar/i }),
    );
    expect(apiPatch).toHaveBeenCalledWith(
      "/api/v1/templates/1",
      expect.not.objectContaining({ name: expect.anything() }),
    );
    expect(apiPatch.mock.calls[0]?.[1]).toHaveProperty(
      "subject_template",
      "Nuevo asunto",
    );
  });

  it("help expandible incluye variables Jinja2 canónicas", async () => {
    const user = userEvent.setup();
    render(<TemplateManager initialTemplates={[_tpl()]} />);
    await user.click(screen.getByRole("button", { name: /wix_intro_es/i }));
    // El <details> está cerrado por defecto; abrir
    const summary = screen.getByText(/variables jinja2 disponibles/i);
    await user.click(summary);
    // `{{ opt_out_url }}` aparece 2 veces en el help (lista de
    // variables + nota explicativa). Confirmamos que al menos 1 está.
    expect(screen.getAllByText("{{ opt_out_url }}").length).toBeGreaterThan(0);
    expect(screen.getAllByText("{{ company_name }}").length).toBeGreaterThan(0);
  });
});
