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

  it("renderiza un step por cada fase canónica del pipeline (17 total)", () => {
    const phases = [_phase("scrape_origin", "completed")];
    render(<PipelineStepper phases={phases} />);
    // Cada step lleva un `aria-label` con "N. Label".
    // v0.24.0 — `asset_uploader` añadido entre transpile_bricks y
    // deploy_wp (16 → 17). `ai_assist` sigue retirado (v0.23.1).
    const items = screen.getAllByRole("listitem");
    expect(items.length).toBe(17);
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
    // v0.23.1 — transpile_bricks vuelve al índice 6 tras quitar ai_assist.
    const target = items[6]!;
    expect(target.innerHTML).toContain("animate-spin");
  });

  it("fase failed usa rojo danger", () => {
    const phases = [_phase("deploy_wp", "failed", { error_log: "SSH timeout" })];
    render(<PipelineStepper phases={phases} />);
    const items = screen.getAllByRole("listitem");
    // v0.24.0 — deploy_wp pasa a índice 8 tras añadir asset_uploader
    // entre transpile_bricks (6) y deploy_wp.
    const target = items[8]!;
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
