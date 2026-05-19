/**
 * Tests del `QaScorecards` (v0.16.0).
 *
 * Cubre: ScoreCard verde/ámbar/rojo según threshold 80/50, CountCard
 * verde si 0 y rojo si >0, BoolCard OK/FAIL/—.
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { QaScorecards } from "../src/app/(app)/projects/[id]/qa/_components/qa-scorecards";

function _report(over: Partial<Parameters<typeof QaScorecards>[0]["report"]> = {}) {
  return {
    lighthouse_perf_desktop: 95,
    lighthouse_perf_mobile: 65,
    lighthouse_a11y_avg: 92,
    lighthouse_best_practices_avg: 88,
    lighthouse_seo_avg: 100,
    html_validator_errors_count: 0,
    html_validator_warnings_count: 0,
    broken_links_count: 0,
    total_links_checked: 42,
    https_valid: true,
    robots_accessible: true,
    sitemap_accessible: true,
    ...over,
  };
}

describe("QaScorecards", () => {
  it("ScoreCard verde si score >= 80", () => {
    render(<QaScorecards report={_report({ lighthouse_perf_desktop: 90 })} />);
    const card = screen.getByText("90");
    expect(card.className).toContain("text-wcm-accent");
  });

  it("ScoreCard ámbar si 50 <= score < 80", () => {
    render(<QaScorecards report={_report({ lighthouse_perf_mobile: 65 })} />);
    const card = screen.getByText("65");
    expect(card.className).toContain("text-wcm-warning");
  });

  it("ScoreCard rojo si score < 50", () => {
    render(<QaScorecards report={_report({ lighthouse_a11y_avg: 30 })} />);
    const card = screen.getByText("30");
    expect(card.className).toContain("text-wcm-danger");
  });

  it("ScoreCard muestra — si null", () => {
    render(<QaScorecards report={_report({ lighthouse_perf_desktop: null })} />);
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("BoolCard OK si true, FAIL si false", () => {
    render(
      <QaScorecards
        report={_report({
          https_valid: true,
          robots_accessible: false,
          sitemap_accessible: null,
        })}
      />,
    );
    expect(screen.getAllByText("OK").length).toBe(1);
    expect(screen.getByText("FAIL")).toBeTruthy();
  });

  it("CountCard rojo si broken_links > 5", () => {
    render(<QaScorecards report={_report({ broken_links_count: 12 })} />);
    const card = screen.getByText("12");
    expect(card.className).toContain("text-wcm-danger");
  });
});
