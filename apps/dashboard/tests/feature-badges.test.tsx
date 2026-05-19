/**
 * Tests del `FeatureBadges` (v0.17.0).
 *
 * Cubre la visibilidad condicional de cada badge (Woo solo si
 * has_ecommerce, WPML solo si is_multilang, Forms solo si la fase
 * rebuild_forms aparece) y el color por estado de la fase
 * (active/pending/skipped/failed).
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { FeatureBadges } from "../src/app/(app)/projects/[id]/_components/feature-badges";
import type { ProjectPhaseRead, ProjectRead } from "@/types/api";

function _project(over: Partial<ProjectRead> = {}): ProjectRead {
  return {
    id: 1,
    lead_id: null,
    client_name: "Test",
    source_url: "https://t.es",
    target_domain: "t.com",
    builder_source: "wix",
    has_ecommerce: false,
    is_multilang: false,
    langs: [],
    primary_lang: null,
    asset_storage: "wp_local",
    preserve_paths: true,
    plan: null,
    hosting_target_json: null,
    theme_styles_origin: null,
    visual_diff_avg_score: null,
    checklist_md_url: null,
    checklist_pdf_url: null,
    status: "running",
    started_at: null,
    completed_at: null,
    estimated_go_live_at: null,
    created_at: "2026-05-19T10:00:00Z",
    updated_at: "2026-05-19T10:00:00Z",
    ...over,
  };
}

function _phase(
  name: string,
  status: ProjectPhaseRead["status"],
  output: Record<string, unknown> | null = null,
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
    output_summary: output,
    created_at: "2026-05-19T10:00:00Z",
    updated_at: "2026-05-19T10:00:00Z",
  };
}

describe("FeatureBadges", () => {
  it("no renderiza nada si ninguna feature aplica", () => {
    const { container } = render(
      <FeatureBadges project={_project()} phases={[]} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("muestra WooCommerce sólo si has_ecommerce=true", () => {
    render(
      <FeatureBadges
        project={_project({ has_ecommerce: true })}
        phases={[_phase("migrate_woo", "completed", { products_migrated: 5 })]}
      />,
    );
    const link = screen.getByRole("link", { name: /WooCommerce/i });
    expect(link.className).toContain("text-wcm-accent");
  });

  it("muestra WPML solo si is_multilang=true", () => {
    render(
      <FeatureBadges
        project={_project({ is_multilang: true })}
        phases={[_phase("configure_wpml", "completed")]}
      />,
    );
    expect(screen.getByText("WPML")).toBeTruthy();
    expect(screen.queryByText("WooCommerce")).toBeNull();
  });

  it("Gravity Forms aparece si la fase rebuild_forms existe", () => {
    render(
      <FeatureBadges
        project={_project()}
        phases={[_phase("rebuild_forms", "completed", { forms_created: 2 })]}
      />,
    );
    expect(screen.getByText("Gravity Forms")).toBeTruthy();
  });

  it("variant skipped cuando WC no disponible", () => {
    render(
      <FeatureBadges
        project={_project({ has_ecommerce: true })}
        phases={[
          _phase("migrate_woo", "completed", { woocommerce_available: false }),
        ]}
      />,
    );
    const link = screen.getByRole("link", { name: /WooCommerce/i });
    expect(link.className).toContain("text-wcm-warning");
  });

  it("variant failed cuando la fase falló", () => {
    render(
      <FeatureBadges
        project={_project({ is_multilang: true })}
        phases={[_phase("configure_wpml", "failed")]}
      />,
    );
    const link = screen.getByRole("link", { name: /WPML/i });
    expect(link.className).toContain("text-wcm-danger");
  });
});
