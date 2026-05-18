/**
 * Tests de los componentes presentacionales del rediseño /campaigns:
 * - `CampaignRunsTable` (histórico paginado, presentacional puro).
 * - `CampaignProgressCard` (activas con polling — testeamos render con
 *   fetch mockeado, sin esperar al intervalo).
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import { CampaignRunsTable } from "../src/app/(app)/campaigns/_components/campaign-runs-table";
import { CampaignProgressCard } from "../src/app/(app)/campaigns/_components/campaign-progress-card";

// ---------- Mock de api.get para CampaignProgressCard ----------

vi.mock("@/lib/api", () => ({
  api: {
    get: vi.fn(),
  },
  ApiError: class ApiError extends Error {},
}));

import { api } from "@/lib/api";

afterEach(() => {
  vi.mocked(api.get).mockReset();
});

// ---------- CampaignRunsTable ----------

const baseRun = {
  id: 1,
  task_id: "abc-123-def",
  sector: "marketing",
  region: "Cáceres",
  target_count: 50,
  status: "completed",
  started_at: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
  completed_at: new Date(Date.now() - 1000 * 60 * 60 * 1.8).toISOString(),
  duration_s: 720,
  leads_count: 38,
  warnings_count: 0,
  error: null,
  created_by_user_id: null,
};

describe("CampaignRunsTable", () => {
  it("renderiza cada run con sector, región, ratio y duración", () => {
    render(<CampaignRunsTable runs={[baseRun]} />);
    expect(screen.getByText("marketing")).toBeInTheDocument();
    expect(screen.getByText(/cáceres/i)).toBeInTheDocument();
    expect(screen.getByText("38/50")).toBeInTheDocument();
    // duración 720s = 12m
    expect(screen.getByText("12m")).toBeInTheDocument();
  });

  it("muestra '<1m' para duraciones < 60s y '—' para duración null", () => {
    render(
      <CampaignRunsTable
        runs={[
          { ...baseRun, id: 1, duration_s: 30 },
          { ...baseRun, id: 2, duration_s: null, status: "running" },
        ]}
      />,
    );
    expect(screen.getByText("<1m")).toBeInTheDocument();
    // Varios "—" aparecen (duración null + indicators sin warnings/error).
    // getAllByText verifica que hay al menos uno.
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("status badge muestra etiqueta castellana por estado", () => {
    render(
      <CampaignRunsTable
        runs={[
          { ...baseRun, id: 1, status: "running" },
          { ...baseRun, id: 2, status: "completed" },
          { ...baseRun, id: 3, status: "failed", error: "boom" },
          { ...baseRun, id: 4, status: "queued" },
        ]}
      />,
    );
    expect(screen.getByText("en curso")).toBeInTheDocument();
    expect(screen.getByText("completada")).toBeInTheDocument();
    expect(screen.getByText("fallida")).toBeInTheDocument();
    expect(screen.getByText("encolada")).toBeInTheDocument();
  });

  it("indica warnings con count y error con badge", () => {
    render(
      <CampaignRunsTable
        runs={[
          { ...baseRun, id: 1, warnings_count: 3 },
          { ...baseRun, id: 2, error: "API key inválida" },
        ]}
      />,
    );
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("error")).toBeInTheDocument();
  });

  it("devuelve null cuando la lista está vacía (delega empty state al padre)", () => {
    const { container } = render(<CampaignRunsTable runs={[]} />);
    expect(container.firstChild).toBeNull();
  });
});

// ---------- CampaignProgressCard ----------

describe("CampaignProgressCard", () => {
  it("no renderiza nada cuando 0 campañas activas", async () => {
    vi.mocked(api.get).mockResolvedValue([]);
    const { container } = render(<CampaignProgressCard />);
    await waitFor(() => {
      expect(vi.mocked(api.get)).toHaveBeenCalledWith("/api/v1/campaigns/active");
    });
    // No hay nada que mostrar
    await new Promise((r) => setTimeout(r, 50));
    expect(container.firstChild).toBeNull();
  });

  it("renderiza header con count y barra de progreso por campaña", async () => {
    vi.mocked(api.get).mockResolvedValue([
      {
        id: 7,
        task_id: "t1",
        sector: "marketing",
        region: "Madrid",
        target_count: 40,
        status: "running",
        started_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
        lead_count: 14,
      },
    ]);
    render(<CampaignProgressCard />);
    await waitFor(() => {
      expect(screen.getByText(/1 campaña en curso/i)).toBeInTheDocument();
    });
    expect(screen.getByText("marketing")).toBeInTheDocument();
    expect(screen.getByText(/madrid/i)).toBeInTheDocument();
    expect(screen.getByText("14 / 40")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
  });

  it("usa plural 'campañas en curso' con 2+", async () => {
    vi.mocked(api.get).mockResolvedValue([
      { id: 1, task_id: "a", sector: "x", region: "y", target_count: 10, status: "running", started_at: null, lead_count: 0 },
      { id: 2, task_id: "b", sector: "x", region: "y", target_count: 10, status: "queued", started_at: null, lead_count: 0 },
    ]);
    render(<CampaignProgressCard />);
    await waitFor(() => {
      expect(screen.getByText(/2 campañas en curso/i)).toBeInTheDocument();
    });
  });
});
