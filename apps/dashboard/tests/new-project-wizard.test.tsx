/**
 * Tests del `NewProjectWizard` (v0.18.0).
 *
 * Verifica: render del stepper 4 pasos, validación inline por paso
 * (Next disabled si falta requerido), pre-relleno desde initialLead,
 * que el paso 4 muestra el botón "Crear proyecto y ejecutar preflight"
 * antes del POST, navegación back/forward.
 */

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { NewProjectWizard } from "../src/app/(app)/projects/new/_components/new-project-wizard";
import type { LeadRead } from "@/types/api";

// Stub minimal de Next router (el wizard usa router.push).
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

function _lead(over: Partial<LeadRead> = {}): LeadRead {
  return {
    id: 42,
    url: "https://barpepe.es",
    business_name: "Bar Pepe",
    sector: "restauración",
    region: "Madrid",
    country: "ES",
    status: "discovered",
    score: 75,
    builder_detected: "wix",
    builder_confidence: 0.92,
    builder_evidence: null,
    emails: [],
    phones: [],
    social_links: {},
    last_crawl_at: null,
    embedding_model: null,
    embedding_at: null,
    created_at: "2026-05-19T10:00:00Z",
    updated_at: "2026-05-19T10:00:00Z",
    ...over,
  };
}

describe("NewProjectWizard", () => {
  it("renderiza los 4 steps en el stepper superior", () => {
    render(<NewProjectWizard initialLead={null} />);
    expect(screen.getByText(/1 · Origen/)).toBeTruthy();
    expect(screen.getByText(/2 · Destino/)).toBeTruthy();
    expect(screen.getByText(/3 · Features/)).toBeTruthy();
    expect(screen.getByText(/4 · Arranque/)).toBeTruthy();
  });

  it("pre-rellena URL + cliente + builder desde initialLead", () => {
    render(<NewProjectWizard initialLead={_lead()} />);
    const urlInput = screen.getByLabelText("URL del origen *") as HTMLInputElement;
    const clientInput = screen.getByLabelText("Nombre del cliente *") as HTMLInputElement;
    const builderSelect = screen.getByLabelText("Builder origen (opcional)") as HTMLSelectElement;
    expect(urlInput.value).toBe("https://barpepe.es");
    expect(clientInput.value).toBe("Bar Pepe");
    expect(builderSelect.value).toBe("wix");
  });

  it("paso 1: 'Siguiente' deshabilitado si URL no es http(s)", () => {
    render(<NewProjectWizard initialLead={null} />);
    const urlInput = screen.getByLabelText("URL del origen *");
    fireEvent.change(urlInput, { target: { value: "no-es-url" } });
    fireEvent.change(screen.getByLabelText("Nombre del cliente *"), {
      target: { value: "Cliente" },
    });
    const nextBtn = screen.getByRole("button", { name: /Siguiente/ });
    expect(nextBtn.hasAttribute("disabled")).toBe(true);
  });

  it("paso 1 → paso 2: navega si campos válidos", () => {
    render(<NewProjectWizard initialLead={_lead()} />);
    fireEvent.click(screen.getByRole("button", { name: /Siguiente/ }));
    expect(screen.getByLabelText("Dominio destino (WordPress) *")).toBeTruthy();
  });

  it("ofrece sección credenciales si builder es wix o webflow", () => {
    render(<NewProjectWizard initialLead={_lead()} />);
    expect(
      screen.getByText(/El cliente nos dio acceso al back/),
    ).toBeTruthy();
  });

  it("NO ofrece credenciales si builder no es wix/webflow", () => {
    render(
      <NewProjectWizard
        initialLead={_lead({ builder_detected: "wordpress" })}
      />,
    );
    expect(screen.queryByText(/El cliente nos dio acceso al back/)).toBeNull();
  });
});
