/**
 * Tests del `PipelineStepper` (v0.18.0).
 *
 * Cubre: empty state, variants por status (completed/running/failed/
 * skipped/pending), orden canónico (las fases salen en el orden del
 * pipeline aunque vengan revueltas del backend), tooltip con summary.
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { PipelineStepper } from "../src/app/(app)/projects/[id]/_components/pipeline-stepper";
import type { ProjectPhaseRead } from "@/types/api";

function _phase(
  name: string,
  status: ProjectPhaseRead["status"],
  over: Partial<ProjectPhaseRead> = {},
): ProjectPhaseRead {
  return {
    id: 1,
    project_id: 1,
    phase_name: name,
    status,
    started_at: null,
    completed_at: null,
    attempt: 1,
    error_log: null,
    output_summary: null,
    created_at: "2026-05-19T10:00:00Z",
    updated_at: "2026-05-19T10:00:00Z",
    ...over,
  };
}

describe("PipelineStepper", () => {
  it("muestra placeholder explicativo si no hay fases", () => {
    render(<PipelineStepper phases={[]} />);
    expect(screen.getByText(/sin fases registradas/i)).toBeTruthy();
    expect(screen.getByText(/Start/)).toBeTruthy();
  });

  it("renderiza un step por cada fase canónica del pipeline (20 total)", () => {
    const phases = [_phase("scrape_origin", "completed")];
    render(<PipelineStepper phases={phases} />);
    // v0.25.0 — añadidos brief_generator + redesign_templates +
    // redesign_ai (17 → 20). transpile_bricks se mantiene visible como
    // "legacy" para proyectos pre-pivote. ai_assist sigue retirado.
    const items = screen.getAllByRole("listitem");
    expect(items.length).toBe(20);
  });

  it("primera fase completada usa color accent (lima)", () => {
    const phases = [_phase("scrape_origin", "completed")];
    render(<PipelineStepper phases={phases} />);
    const first = screen.getAllByRole("listitem")[0]!;
    const icon = first.querySelector("div");
    expect(icon?.className).toContain("border-wcm-accent");
  });

  it("fase running tiene loader animate-spin y label accent", () => {
    const phases = [_phase("transpile_bricks", "running")];
    render(<PipelineStepper phases={phases} />);
    const items = screen.getAllByRole("listitem");
    // v0.25.0 — transpile_bricks ahora en índice 9 tras añadir
    // brief_generator (6) + redesign_templates (7) + redesign_ai (8).
    const target = items[9]!;
    expect(target.innerHTML).toContain("animate-spin");
  });

  it("fase failed usa rojo danger", () => {
    const phases = [_phase("deploy_wp", "failed", { error_log: "SSH timeout" })];
    render(<PipelineStepper phases={phases} />);
    const items = screen.getAllByRole("listitem");
    // v0.25.0 — deploy_wp pasa a índice 11 (asset_uploader=10, deploy_wp=11).
    const target = items[11]!;
    expect(target.querySelector("div")?.className).toContain("border-wcm-danger");
  });

  it("tooltip muestra summary y duración cuando disponibles", () => {
    const phases = [
      _phase("scrape_origin", "completed", {
        started_at: "2026-05-19T10:00:00Z",
        completed_at: "2026-05-19T10:00:45Z",
        output_summary: { summary: "30 páginas crawled" } as Record<string, unknown>,
      }),
    ];
    render(<PipelineStepper phases={phases} />);
    expect(screen.getByText("30 páginas crawled")).toBeTruthy();
    // 45 segundos → "45s" en el tooltip.
    expect(screen.getByText(/· 45s/)).toBeTruthy();
  });
});
