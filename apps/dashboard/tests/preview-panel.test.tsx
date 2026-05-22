/**
 * Tests del PreviewPanel — v0.25.1 B7.
 *
 * Verifica:
 * - renderiza brief + lista de páginas
 * - botón Regenerar dispara POST /preview/regenerate-page con el slug
 * - botón Aprobar dispara POST /preview/approve tras confirmar
 * - modal de Editar Brief envía PATCH /brief con los campos editados
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const apiPost = vi.fn();
const apiPatch = vi.fn();
const routerRefresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: routerRefresh, push: vi.fn() }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    post: (...args: unknown[]) => apiPost(...args),
    patch: (...args: unknown[]) => apiPatch(...args),
  },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(m: string, s: number) {
      super(m);
      this.status = s;
    }
  },
}));

import { PreviewPanel } from "../src/app/(app)/projects/[id]/preview/_components/preview-panel";

const BRIEF = {
  business: {
    name: "Mariya Design",
    description: "Estudio de diseño artesanal",
    sector: "agency",
    tone_of_voice: "friendly",
    target_audience: "PYMEs creativas",
    usps: ["Artesanal", "Único"],
  },
};

const PAGES = [
  {
    slug: "home",
    title: "Inicio",
    intent: "landing",
    n_sections: 4,
    bricks_page_id: 11,
    wp_post_id: 101,
    wp_post_status: "draft",
    last_regenerated_at: null,
  },
  {
    slug: "contacto",
    title: "Contacto",
    intent: null,
    n_sections: 2,
    bricks_page_id: 12,
    wp_post_id: null,
    wp_post_status: null,
    last_regenerated_at: "2026-05-22T10:00:00Z",
  },
];

afterEach(() => {
  vi.clearAllMocks();
});

describe("PreviewPanel", () => {
  it("renderiza brief + lista de páginas con counts", () => {
    render(
      <PreviewPanel
        projectId={42}
        designMethod="templates"
        brief={BRIEF}
        pages={PAGES}
        projectStatus="ready_for_preview"
      />,
    );
    expect(screen.getByText("Mariya Design")).toBeInTheDocument();
    expect(
      screen.getByText("Estudio de diseño artesanal"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Preview · 2 páginas/)).toBeInTheDocument();
    expect(screen.getByText("Inicio")).toBeInTheDocument();
    expect(screen.getByText("Contacto")).toBeInTheDocument();
    expect(screen.getByText(/4 secciones/)).toBeInTheDocument();
  });

  it("regenerate dispara POST /preview/regenerate-page con el slug", async () => {
    apiPost.mockResolvedValueOnce({ task_id: "abc" });
    render(
      <PreviewPanel
        projectId={42}
        designMethod="templates"
        brief={BRIEF}
        pages={PAGES}
        projectStatus="ready_for_preview"
      />,
    );
    const buttons = screen.getAllByText("Regenerar");
    const firstButton = buttons[0];
    if (!firstButton) throw new Error("no Regenerar button found");
    fireEvent.click(firstButton);
    await waitFor(() => expect(apiPost).toHaveBeenCalledTimes(1));
    expect(apiPost).toHaveBeenCalledWith(
      "/api/v1/projects/42/preview/regenerate-page",
      { slug: "home" },
    );
  });

  it("Aprobar y publicar pide confirm y dispara POST /preview/approve", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    apiPost.mockResolvedValueOnce({});
    render(
      <PreviewPanel
        projectId={42}
        designMethod="ai"
        brief={BRIEF}
        pages={PAGES}
        projectStatus="ready_for_preview"
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /Aprobar y publicar/ }),
    );
    expect(confirmSpy).toHaveBeenCalled();
    await waitFor(() => expect(apiPost).toHaveBeenCalledTimes(1));
    expect(apiPost).toHaveBeenCalledWith(
      "/api/v1/projects/42/preview/approve",
    );
    confirmSpy.mockRestore();
  });

  it("Editar Brief abre modal y PATCH guarda los campos", async () => {
    apiPatch.mockResolvedValueOnce({});
    render(
      <PreviewPanel
        projectId={42}
        designMethod="templates"
        brief={BRIEF}
        pages={PAGES}
        projectStatus="ready_for_preview"
      />,
    );
    fireEvent.click(screen.getByText("Editar Brief"));
    const desc = await screen.findByDisplayValue(
      "Estudio de diseño artesanal",
    );
    fireEvent.change(desc, { target: { value: "Nueva descripción" } });
    fireEvent.click(screen.getByText("Guardar"));
    await waitFor(() => expect(apiPatch).toHaveBeenCalledTimes(1));
    const firstCall = apiPatch.mock.calls[0];
    if (!firstCall) throw new Error("apiPatch not called");
    const [path, body] = firstCall;
    expect(path).toBe("/api/v1/projects/42/brief");
    expect(body).toMatchObject({
      business_description: "Nueva descripción",
      business_sector: "agency",
      target_audience: "PYMEs creativas",
      tone_of_voice: "friendly",
      usps_json: ["Artesanal", "Único"],
    });
  });

  it("regenerate-section dispara POST con el design_method override", async () => {
    apiPost.mockResolvedValueOnce({ task_id: "x" });
    const pagesWithSections = [
      {
        ...PAGES[0]!,
        sections: [
          {
            type: "hero",
            design_method: "ai",
            has_ai_image: false,
            is_placeholder: false,
            asset_id: null,
            headline: "Bienvenido",
          },
        ],
      },
    ];
    render(
      <PreviewPanel
        projectId={42}
        designMethod={null}
        brief={BRIEF}
        pages={pagesWithSections}
        projectStatus="ready_for_preview"
      />,
    );
    // Cambia el dropdown design_method → templates → dispara POST.
    const select = screen.getByTitle("Cambiar método y regenerar");
    fireEvent.change(select, { target: { value: "templates" } });
    await waitFor(() => expect(apiPost).toHaveBeenCalledTimes(1));
    expect(apiPost).toHaveBeenCalledWith(
      "/api/v1/projects/42/preview/regenerate-section",
      { slug: "home", section_index: 0, design_method: "templates" },
    );
  });

  it("regenerate-image dispara POST si la sección tiene imagen IA", async () => {
    apiPost.mockResolvedValueOnce({ task_id: "y" });
    const pagesWithAIImage = [
      {
        ...PAGES[0]!,
        sections: [
          {
            type: "hero",
            design_method: "ai",
            has_ai_image: true,
            is_placeholder: false,
            asset_id: 99,
            headline: null,
          },
        ],
      },
    ];
    render(
      <PreviewPanel
        projectId={42}
        designMethod={null}
        brief={BRIEF}
        pages={pagesWithAIImage}
        projectStatus="ready_for_preview"
      />,
    );
    const imgBtn = screen.getByTitle(
      "Regenerar la imagen IA de esta sección",
    );
    fireEvent.click(imgBtn);
    await waitFor(() => expect(apiPost).toHaveBeenCalledTimes(1));
    expect(apiPost).toHaveBeenCalledWith(
      "/api/v1/projects/42/preview/regenerate-image",
      { slug: "home", section_index: 0 },
    );
  });

  it("badge 'calidad baja' aparece cuando asset_is_low_quality y sin imagen IA (v0.27.0)", () => {
    const pagesWithLowQuality = [
      {
        ...PAGES[0]!,
        sections: [
          {
            type: "hero",
            design_method: "templates",
            has_ai_image: false,
            is_placeholder: false,
            asset_id: 5,
            headline: null,
            asset_quality_score: 0.3,
            asset_quality_flags: ["low_resolution", "obsolete_format"],
            asset_is_low_quality: true,
          },
        ],
      },
    ];
    render(
      <PreviewPanel
        projectId={42}
        designMethod={null}
        brief={BRIEF}
        pages={pagesWithLowQuality}
        projectStatus="ready_for_preview"
      />,
    );
    expect(screen.getByText("calidad baja")).toBeInTheDocument();
    // botón "imagen" también disponible para regenerar con IA.
    expect(
      screen.getByTitle(
        "Generar imagen IA en sustitución del origen (calidad baja)",
      ),
    ).toBeInTheDocument();
  });

  it("budget tracking se muestra cuando hay coste IA > 0", () => {
    render(
      <PreviewPanel
        projectId={42}
        designMethod="ai"
        brief={BRIEF}
        pages={PAGES}
        projectStatus="ready_for_preview"
        imageGenerationCostUsd={0.123}
        imageGenerationBudgetUsd={1.0}
      />,
    );
    expect(screen.getByText(/\$0.1230/)).toBeInTheDocument();
    expect(screen.getByText(/budget/)).toBeInTheDocument();
  });

  it("sin brief renderiza el panel sin caer", () => {
    render(
      <PreviewPanel
        projectId={42}
        designMethod={null}
        brief={null}
        pages={[]}
        projectStatus="running"
      />,
    );
    expect(
      screen.getByText(/Sin páginas generadas todavía/),
    ).toBeInTheDocument();
  });
});
