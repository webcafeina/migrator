/**
 * Tests de los componentes shared del rediseño /projects/[id]:
 * - `PhaseProgressBar` — barra multi-segmento con counts.
 * - `ProjectTabs` (Client) — 3 tabs con active state y badge de
 *   residuales abiertas.
 * - `ProjectHeader` — composición de breadcrumb + título + URL + meta +
 *   tabs. Smoke render.
 * - `ProjectPhasesTimeline` — timeline vertical con icono por status.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { renderToString } from "react-dom/server";

// Mock next/navigation para ProjectTabs.
const usePathnameMock = vi.fn(() => "/projects/1");
vi.mock("next/navigation", () => ({
  usePathname: () => usePathnameMock(),
}));

import { PhaseProgressBar } from "../src/app/(app)/projects/[id]/_components/phase-progress-bar";
import { ProjectHeader } from "../src/app/(app)/projects/[id]/_components/project-header";
import { ProjectPhasesTimeline } from "../src/app/(app)/projects/[id]/_components/project-phases-timeline";
import { ProjectTabs } from "../src/app/(app)/projects/[id]/_components/project-tabs";
import type { ProjectPhaseRead, ProjectRead } from "@/types/api";

afterEach(() => {
  usePathnameMock.mockReset();
  usePathnameMock.mockReturnValue("/projects/1");
});

// ---------- PhaseProgressBar ----------

describe("PhaseProgressBar", () => {
  it("muestra N/M con total>0", () => {
    render(
      <PhaseProgressBar total={15} completed={5} failed={0} running={1} />,
    );
    expect(screen.getByText("5/15")).toBeInTheDocument();
  });

  it("'0/0' y barra vacía cuando total=0", () => {
    render(
      <PhaseProgressBar total={0} completed={0} failed={0} running={0} />,
    );
    expect(screen.getByText("0/0")).toBeInTheDocument();
  });

  it("renderiza segmentos con porcentajes correctos", () => {
    const html = renderToString(
      <PhaseProgressBar total={10} completed={4} failed={1} running={2} />,
    );
    expect(html).toContain("width:40%"); // completed
    expect(html).toContain("width:10%"); // failed
    expect(html).toContain("width:20%"); // running
  });
});

// ---------- ProjectTabs ----------

const TAB_LABELS = ["Overview", "Checklist", "Visual diff"];

describe("ProjectTabs", () => {
  it("renderiza los 3 tabs con sus etiquetas", () => {
    render(<ProjectTabs projectId={1} />);
    for (const label of TAB_LABELS) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("Overview activo cuando pathname = /projects/1 exacto", () => {
    usePathnameMock.mockReturnValue("/projects/1");
    render(<ProjectTabs projectId={1} />);
    expect(screen.getByText("Overview").closest("a")).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByText("Checklist").closest("a")).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("Checklist activo cuando pathname = /projects/1/checklist", () => {
    usePathnameMock.mockReturnValue("/projects/1/checklist");
    render(<ProjectTabs projectId={1} />);
    expect(screen.getByText("Checklist").closest("a")).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("badge de residuales abiertas visible en Checklist con count>0", () => {
    render(<ProjectTabs projectId={1} counts={{ residualOpen: 4 }} />);
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("badge NO visible si residualOpen=0", () => {
    render(<ProjectTabs projectId={1} counts={{ residualOpen: 0 }} />);
    // El texto "0" no debe aparecer junto al label Checklist
    const checklist = screen.getByText("Checklist").closest("a");
    expect(checklist?.textContent).not.toMatch(/Checklist\s*0/);
  });

  it("links a las rutas correctas con projectId", () => {
    render(<ProjectTabs projectId={42} />);
    expect(screen.getByText("Overview").closest("a")).toHaveAttribute(
      "href",
      "/projects/42",
    );
    expect(screen.getByText("Checklist").closest("a")).toHaveAttribute(
      "href",
      "/projects/42/checklist",
    );
    expect(screen.getByText("Visual diff").closest("a")).toHaveAttribute(
      "href",
      "/projects/42/diff",
    );
  });
});

// ---------- ProjectHeader (smoke) ----------

function _project(over: Partial<ProjectRead> = {}): ProjectRead {
  return {
    id: 1,
    lead_id: 42,
    client_name: "Bar Pepe",
    source_url: "https://barpepe.es",
    target_domain: "barpepe.com",
    builder_source: "wix",
    has_ecommerce: false,
    is_multilang: false,
    langs: [],
    primary_lang: null,
    asset_storage: "wp_local",
    preserve_paths: true,
    status: "running",
    started_at: null,
    completed_at: null,
    estimated_go_live_at: null,
    visual_diff_avg_score: null,
    created_at: "2026-05-15T10:00:00Z",
    updated_at: "2026-05-15T12:00:00Z",
    ...over,
  } as ProjectRead;
}

describe("ProjectHeader", () => {
  it("renderiza cliente, ID, URL y breadcrumb", () => {
    render(
      <ProjectHeader
        project={_project()}
        summary={{
          project_id: 1,
          lead_origin: null,
          phases_total: 15,
          phases_completed: 5,
          phases_failed: 0,
          phases_running: 1,
          phases_pending: 9,
          current_phase_name: "bricks_transpiler",
          residual_total: 0,
          residual_open: 0,
          residual_done: 0,
        }}
      />,
    );
    expect(screen.getByText("Bar Pepe")).toBeInTheDocument();
    expect(screen.getByText("Proyecto · #1")).toBeInTheDocument();
    expect(screen.getByText(/barpepe\.es/)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /proyectos/i }),
    ).toHaveAttribute("href", "/projects");
    // Fase actual en la meta line
    expect(screen.getByText("bricks_transpiler")).toBeInTheDocument();
  });

  it("muestra link al lead origen cuando existe", () => {
    render(
      <ProjectHeader
        project={_project()}
        summary={{
          project_id: 1,
          lead_origin: {
            id: 42,
            business_name: "Hostel Papy",
            score: 88,
            builder_detected: "wordpress",
          },
          phases_total: 0,
          phases_completed: 0,
          phases_failed: 0,
          phases_running: 0,
          phases_pending: 0,
          current_phase_name: null,
          residual_total: 0,
          residual_open: 0,
          residual_done: 0,
        }}
      />,
    );
    const link = screen.getByRole("link", { name: /lead origen.*hostel papy/i });
    expect(link).toHaveAttribute("href", "/leads?selected=42");
    expect(link.textContent).toContain("score 88");
  });

  it("omite la sección lead si lead_origin es null", () => {
    render(
      <ProjectHeader
        project={_project({ lead_id: null })}
        summary={{
          project_id: 1,
          lead_origin: null,
          phases_total: 0,
          phases_completed: 0,
          phases_failed: 0,
          phases_running: 0,
          phases_pending: 0,
          current_phase_name: null,
          residual_total: 0,
          residual_open: 0,
          residual_done: 0,
        }}
      />,
    );
    expect(screen.queryByText(/lead origen/i)).toBeNull();
  });

  it("renderiza acciones en el slot cuando se pasan", () => {
    render(
      <ProjectHeader
        project={_project()}
        actions={<button type="button">Start</button>}
        summary={{
          project_id: 1,
          lead_origin: null,
          phases_total: 0,
          phases_completed: 0,
          phases_failed: 0,
          phases_running: 0,
          phases_pending: 0,
          current_phase_name: null,
          residual_total: 0,
          residual_open: 0,
          residual_done: 0,
        }}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Start" }),
    ).toBeInTheDocument();
  });
});

// ---------- ProjectPhasesTimeline ----------

function _phase(over: Partial<ProjectPhaseRead> = {}): ProjectPhaseRead {
  return {
    id: 1,
    project_id: 1,
    phase_name: "scrape_origin",
    status: "completed",
    attempt: 1,
    started_at: "2026-05-15T10:00:00Z",
    completed_at: "2026-05-15T10:02:30Z",
    error_log: null,
    output_summary: null,
    created_at: "2026-05-15T10:00:00Z",
    updated_at: "2026-05-15T10:02:30Z",
    ...over,
  } as ProjectPhaseRead;
}

describe("ProjectPhasesTimeline", () => {
  it("renderiza una entrada por fase con nombre", () => {
    render(
      <ProjectPhasesTimeline
        phases={[
          _phase({ id: 1, phase_name: "scrape_origin" }),
          _phase({ id: 2, phase_name: "bricks_transpiler", status: "running" }),
        ]}
      />,
    );
    expect(screen.getByText("scrape_origin")).toBeInTheDocument();
    expect(screen.getByText("bricks_transpiler")).toBeInTheDocument();
    expect(screen.getByText(/en curso/i)).toBeInTheDocument();
    expect(screen.getByText("ok")).toBeInTheDocument();
  });

  it("muestra badge de reintento si attempt > 1", () => {
    render(
      <ProjectPhasesTimeline
        phases={[
          _phase({ attempt: 3, status: "failed" }),
        ]}
      />,
    );
    expect(screen.getByText(/intento 3/i)).toBeInTheDocument();
    expect(screen.getByText("fallo")).toBeInTheDocument();
  });

  it("muestra error_log en color danger cuando existe", () => {
    render(
      <ProjectPhasesTimeline
        phases={[
          _phase({
            status: "failed",
            error_log: "Timeout esperando renderizado de la SPA",
          }),
        ]}
      />,
    );
    expect(
      screen.getByText(/timeout esperando renderizado/i),
    ).toBeInTheDocument();
  });

  it("empty state explicativo cuando 0 fases", () => {
    render(<ProjectPhasesTimeline phases={[]} />);
    expect(screen.getByText(/pipeline sin arrancar todavía/i)).toBeInTheDocument();
    expect(screen.getByText(/start.*encolar el pipeline/i)).toBeInTheDocument();
  });
});
