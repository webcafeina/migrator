/**
 * Tests del DraftBanner reactivo (v0.13.3).
 *
 * El banner ahora fetcha la sequence más reciente del lead y renderiza
 * copy/color/CTA según el `sequence.status`. Antes solo mostraba un
 * mensaje fijo ámbar acoplado a `lead.status === "outreach_prepared"`.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const apiGet = vi.fn();

vi.mock("@/lib/api", () => ({
  api: { get: (...args: unknown[]) => apiGet(...args) },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(m: string, s: number) {
      super(m);
      this.status = s;
    }
  },
}));

import { DraftBanner } from "../src/app/(app)/leads/_components/draft-banner";

function _seq(over: Record<string, unknown> = {}) {
  return {
    id: 1,
    lead_id: 5,
    template_name: "wix_intro_es",
    name: "Outreach inicial · Test",
    channel: "email",
    steps_json: [],
    status: "draft_pending_review",
    legal_validation_passed: true,
    legal_validator_version: "v1.0",
    created_at: "2026-05-18T10:00:00Z",
    updated_at: "2026-05-18T10:00:00Z",
    ...over,
  };
}

beforeEach(() => {
  apiGet.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("DraftBanner reactivo", () => {
  it("no se renderiza si el lead no tiene secuencia", async () => {
    apiGet.mockResolvedValue([]);
    const { container } = render(<DraftBanner leadId={5} />);
    await waitFor(() => expect(apiGet).toHaveBeenCalled());
    // Banner devuelve null cuando no hay sequence.
    expect(container.firstChild).toBeNull();
  });

  it("DRAFT_PENDING_REVIEW + legal_passed → 'Borrador preparado' ámbar + CTA Revisar", async () => {
    apiGet.mockResolvedValue([_seq()]);
    render(<DraftBanner leadId={5} />);
    await screen.findByText(/borrador de contacto preparado/i);
    expect(screen.getByText(/pendiente de revisión humana/i)).toBeInTheDocument();
    const cta = screen.getByRole("link", { name: /revisar/i });
    expect(cta).toHaveAttribute("href", "#outreach");
    // ámbar (wcm-warning) en el título
    const title = screen.getByText(/borrador de contacto preparado/i);
    expect(title.className).toContain("wcm-warning");
  });

  it("DRAFT_PENDING_REVIEW + !legal_passed → 'NO aprobable' rojo + CTA Editar", async () => {
    apiGet.mockResolvedValue([_seq({ legal_validation_passed: false })]);
    render(<DraftBanner leadId={5} />);
    await screen.findByText(/borrador no aprobable/i);
    expect(screen.getByText(/validación legal falla/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /editar/i })).toBeVisible();
    const title = screen.getByText(/borrador no aprobable/i);
    expect(title.className).toContain("wcm-danger");
  });

  it("READY → 'Correos listos para enviar' lima + CTA Enviar", async () => {
    apiGet.mockResolvedValue([_seq({ status: "ready" })]);
    render(<DraftBanner leadId={5} />);
    await screen.findByText(/correos listos para enviar/i);
    expect(screen.getByText(/aprobad.*enviar/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /enviar/i })).toBeVisible();
    const title = screen.getByText(/correos listos para enviar/i);
    expect(title.className).toContain("wcm-accent");
  });

  it("IN_PROGRESS → 'Enviando contacto' lima animado + CTA Ver progreso", async () => {
    apiGet.mockResolvedValue([_seq({ status: "in_progress" })]);
    render(<DraftBanner leadId={5} />);
    await screen.findByText(/enviando contacto/i);
    expect(screen.getByRole("link", { name: /ver progreso/i })).toBeVisible();
  });

  it("PAUSED → 'Contacto pausado' ámbar + CTA Reanudar", async () => {
    apiGet.mockResolvedValue([_seq({ status: "paused" })]);
    render(<DraftBanner leadId={5} />);
    await screen.findByText(/contacto pausado/i);
    expect(screen.getByRole("link", { name: /reanudar/i })).toBeVisible();
  });

  it("COMPLETED → 'Contacto completado' gris + CTA Ver historial", async () => {
    apiGet.mockResolvedValue([_seq({ status: "completed" })]);
    render(<DraftBanner leadId={5} />);
    await screen.findByText(/contacto completado/i);
    expect(screen.getByRole("link", { name: /ver historial/i })).toBeVisible();
  });

  it("CANCELLED → no se renderiza banner", async () => {
    apiGet.mockResolvedValue([_seq({ status: "cancelled" })]);
    const { container } = render(<DraftBanner leadId={5} />);
    await waitFor(() => expect(apiGet).toHaveBeenCalled());
    expect(container.firstChild).toBeNull();
  });

  it("OPTED_OUT → no se renderiza banner", async () => {
    apiGet.mockResolvedValue([_seq({ status: "opted_out" })]);
    const { container } = render(<DraftBanner leadId={5} />);
    await waitFor(() => expect(apiGet).toHaveBeenCalled());
    expect(container.firstChild).toBeNull();
  });

  it("status uppercase del API ('READY' literal) también funciona — tolerancia case", async () => {
    apiGet.mockResolvedValue([_seq({ status: "READY" })]);
    render(<DraftBanner leadId={5} />);
    await screen.findByText(/correos listos para enviar/i);
  });

  it("fetch falla → no se renderiza (degradación silenciosa)", async () => {
    apiGet.mockRejectedValue(new Error("api down"));
    const { container } = render(<DraftBanner leadId={5} />);
    await waitFor(() => expect(apiGet).toHaveBeenCalled());
    expect(container.firstChild).toBeNull();
  });
});
