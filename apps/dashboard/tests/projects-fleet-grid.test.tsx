/**
 * Tests del `ProjectsFleetGrid` (v0.19.0).
 *
 * Cubre: render de N tarjetas, mini-stepper con dots de colores por
 * status del bucket, badges Woo/WPML/builder cuando aplica, scoreBadge
 * según rango, link a /projects/[id].
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import {
  ProjectsFleetGrid,
  type ProjectFleetItem,
} from "../src/app/(app)/projects/_components/projects-fleet-grid";

function _project(over: Partial<ProjectFleetItem> = {}): ProjectFleetItem {
  return {
    id: 7,
    client_name: "Bar Pepe",
    source_url: "https://barpepe.es/",
    target_domain: "barpepe.com",
    builder_source: "wix",
    status: "running",
    visual_diff_avg_score: 0.91,
    has_ecommerce: false,
    is_multilang: false,
    started_at: "2026-05-19T12:00:00Z",
    phase_summary: {
      scrape: "completed",
      transpile: "completed",
      deploy: "running",
      qa: "pending",
      notify: "pending",
    },
    current_phase_name: "deploy_wp",
    ...over,
  };
}

describe("ProjectsFleetGrid", () => {
  it("renderiza una tarjeta por proyecto", () => {
    const projects = [_project({ id: 1 }), _project({ id: 2 }), _project({ id: 3 })];
    render(<ProjectsFleetGrid projects={projects} />);
    expect(screen.getAllByRole("link").length).toBe(3);
  });

  it("link de la tarjeta apunta a /projects/[id]", () => {
    render(<ProjectsFleetGrid projects={[_project({ id: 42 })]} />);
    const link = screen.getByRole("link");
    expect(link.getAttribute("href")).toBe("/projects/42");
  });

  it("mini-stepper pinta 5 dots con aria-label por bucket", () => {
    render(<ProjectsFleetGrid projects={[_project()]} />);
    expect(screen.getByLabelText("Scrape: completed")).toBeTruthy();
    expect(screen.getByLabelText("Bricks: completed")).toBeTruthy();
    expect(screen.getByLabelText("Deploy: running")).toBeTruthy();
    expect(screen.getByLabelText("QA: pending")).toBeTruthy();
    expect(screen.getByLabelText("Notify: pending")).toBeTruthy();
  });

  it("dot running tiene animación pulse", () => {
    render(<ProjectsFleetGrid projects={[_project()]} />);
    const deploy = screen.getByLabelText("Deploy: running");
    expect(deploy.className).toContain("animate-pulse");
  });

  it("badges Woo/WPML visibles solo si las flags están activas", () => {
    render(
      <ProjectsFleetGrid
        projects={[_project({ has_ecommerce: true, is_multilang: true })]}
      />,
    );
    expect(screen.getByText("Woo")).toBeTruthy();
    expect(screen.getByText("WPML")).toBeTruthy();
  });

  it("ScoreBadge verde si score >= 0.85", () => {
    render(<ProjectsFleetGrid projects={[_project({ visual_diff_avg_score: 0.9 })]} />);
    const badge = screen.getByText(/diff 90%/);
    expect(badge.className).toContain("text-wcm-accent");
  });

  it("StatusPill 'revertido' rojo si status=rolled_back", () => {
    render(<ProjectsFleetGrid projects={[_project({ status: "rolled_back" })]} />);
    expect(screen.getByText("revertido")).toBeTruthy();
  });

  it("ScoreBadge muestra '—' si score es null", () => {
    render(<ProjectsFleetGrid projects={[_project({ visual_diff_avg_score: null })]} />);
    expect(screen.getByText(/diff —/)).toBeTruthy();
  });
});
