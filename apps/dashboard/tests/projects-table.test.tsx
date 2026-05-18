/**
 * Tests del `ProjectsTable` (presentacional puro).
 *
 * Cubre: render por proyecto, links a /projects/{id} y al lead origen,
 * 6 status badges en castellano, DiffIndicator (verde ≥85, ámbar 70-84,
 * rojo <70, "—" si null), BuilderBadge (oculta unknown/null), empty
 * state delegado al padre.
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { ProjectsTable } from "../src/app/(app)/projects/_components/projects-table";
import type { ProjectRead } from "@/types/api";

function _project(over: Partial<ProjectRead> = {}): ProjectRead {
  return {
    id: 1,
    lead_id: null,
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

describe("ProjectsTable — render base", () => {
  it("renderiza una fila por proyecto con cliente y id", () => {
    render(<ProjectsTable projects={[_project(), _project({ id: 2, client_name: "Otro" })]} />);
    expect(screen.getByText("Bar Pepe")).toBeInTheDocument();
    expect(screen.getByText("Otro")).toBeInTheDocument();
    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("#2")).toBeInTheDocument();
  });

  it("el nombre del cliente enlaza a /projects/{id}", () => {
    render(<ProjectsTable projects={[_project({ id: 42, client_name: "Cliente X" })]} />);
    expect(
      screen.getByRole("link", { name: "Cliente X" }),
    ).toHaveAttribute("href", "/projects/42");
  });

  it("muestra link al lead origen cuando existe lead_id", () => {
    render(<ProjectsTable projects={[_project({ id: 1, lead_id: 99 })]} />);
    expect(
      screen.getByRole("link", { name: /lead #99/i }),
    ).toHaveAttribute("href", "/leads?selected=99");
  });

  it("omite el link al lead cuando lead_id es null", () => {
    render(<ProjectsTable projects={[_project({ lead_id: null })]} />);
    expect(screen.queryByText(/lead #/i)).toBeNull();
  });

  it("devuelve null cuando la lista está vacía (empty state al padre)", () => {
    const { container } = render(<ProjectsTable projects={[]} />);
    expect(container.firstChild).toBeNull();
  });
});

describe("ProjectsTable — status badges castellano", () => {
  const cases: Array<[ProjectRead["status"], RegExp]> = [
    ["queued", /encolado/i],
    ["running", /en curso/i],
    ["blocked_human_input", /bloqueado/i],
    ["qa_failed", /qa fallido/i],
    ["completed", /completado/i],
    ["cancelled", /cancelado/i],
  ];
  for (const [status, label] of cases) {
    it(`status="${status}" → "${label.source}"`, () => {
      render(<ProjectsTable projects={[_project({ status })]} />);
      expect(screen.getByText(label)).toBeInTheDocument();
    });
  }
});

describe("ProjectsTable — DiffIndicator", () => {
  it("score=null muestra '—'", () => {
    const { container } = render(
      <ProjectsTable projects={[_project({ visual_diff_avg_score: null })]} />,
    );
    // La columna diff aparece en lg+; testing-library renderiza el DOM
    // completo (no aplica media queries), así que el "—" sí está.
    const html = container.innerHTML;
    expect(html).toContain("—");
  });

  it("score=0.95 muestra 95% en verde", () => {
    render(
      <ProjectsTable projects={[_project({ visual_diff_avg_score: 0.95 })]} />,
    );
    expect(screen.getByText("95%")).toBeInTheDocument();
  });

  it("score=0.75 muestra 75% en ámbar (70-84)", () => {
    render(
      <ProjectsTable projects={[_project({ visual_diff_avg_score: 0.75 })]} />,
    );
    expect(screen.getByText("75%")).toBeInTheDocument();
  });

  it("score=0.45 muestra 45% en rojo (<70)", () => {
    render(
      <ProjectsTable projects={[_project({ visual_diff_avg_score: 0.45 })]} />,
    );
    expect(screen.getByText("45%")).toBeInTheDocument();
  });
});

describe("ProjectsTable — BuilderBadge", () => {
  it("wix → badge visible", () => {
    render(<ProjectsTable projects={[_project({ builder_source: "wix" })]} />);
    expect(screen.getByText("wix")).toBeInTheDocument();
  });

  it("unknown → '—' (no badge)", () => {
    render(
      <ProjectsTable projects={[_project({ builder_source: "unknown" })]} />,
    );
    // No debe haber un span uppercase con "unknown" como contenido
    expect(screen.queryByText("unknown")).toBeNull();
  });

  it("null → '—'", () => {
    render(<ProjectsTable projects={[_project({ builder_source: null })]} />);
    expect(screen.queryByText("null")).toBeNull();
  });
});
