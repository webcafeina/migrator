/**
 * Tests del `DiffGallery` (v0.16.0).
 *
 * Cubre: empty state, render thumbnails con badge por score, abrir
 * modal full-size al click en thumbnail, fallback "(local)" si URL
 * empieza por `file://` (R2 no configurado).
 */

import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { DiffGallery } from "../src/app/(app)/projects/[id]/diff/_components/diff-gallery";

interface VisualDiffRow {
  id: number;
  page_path: string;
  source_screenshot_url: string | null;
  target_screenshot_url: string | null;
  overlay_url: string | null;
  score: number | null;
  viewport_width: number;
}

function _row(over: Partial<VisualDiffRow> = {}): VisualDiffRow {
  return {
    id: 1,
    page_path: "/",
    source_screenshot_url: "https://r2.example/src.png",
    target_screenshot_url: "https://r2.example/tgt.png",
    overlay_url: "https://r2.example/ovl.png",
    score: 0.92,
    viewport_width: 1280,
    ...over,
  };
}

describe("DiffGallery", () => {
  it("muestra placeholder cuando no hay páginas", () => {
    render(<DiffGallery pages={[]} />);
    expect(screen.getByText(/no hay comparaciones visuales/i)).toBeTruthy();
  });

  it("pinta badge verde para score >= 0.85", () => {
    render(<DiffGallery pages={[_row({ score: 0.9 })]} />);
    const badge = screen.getByText("90%");
    expect(badge.className).toContain("text-wcm-accent");
  });

  it("pinta badge ámbar para score entre 0.7 y 0.85", () => {
    render(<DiffGallery pages={[_row({ score: 0.75 })]} />);
    const badge = screen.getByText("75%");
    expect(badge.className).toContain("text-wcm-warning");
  });

  it("pinta badge rojo para score < 0.7", () => {
    render(<DiffGallery pages={[_row({ score: 0.4 })]} />);
    const badge = screen.getByText("40%");
    expect(badge.className).toContain("text-wcm-danger");
  });

  it("muestra fallback (local) para URLs file://", () => {
    render(
      <DiffGallery
        pages={[
          _row({
            source_screenshot_url: "file:///tmp/x.png",
            target_screenshot_url: "file:///tmp/y.png",
            overlay_url: "file:///tmp/z.png",
          }),
        ]}
      />,
    );
    expect(screen.getAllByText("(local)").length).toBe(3);
  });

  it("abre modal al hacer click en thumbnail", () => {
    render(
      <DiffGallery pages={[_row({ page_path: "/contacto" })]} />,
    );
    const btn = screen.getByLabelText("Origen /contacto");
    fireEvent.click(btn);
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByText("Cerrar")).toBeTruthy();
  });
});
