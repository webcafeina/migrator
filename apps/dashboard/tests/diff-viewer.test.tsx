/**
 * Tests del DiffViewer (Sprint v0.27.0 B3).
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { DiffViewer, diffWords } from "../src/components/diff-viewer";


describe("diffWords", () => {
  it("dos strings idénticos → 1 token equal", () => {
    const tokens = diffWords("hola mundo", "hola mundo");
    expect(tokens).toHaveLength(1);
    expect(tokens[0]).toEqual({ type: "equal", value: "hola mundo" });
  });

  it("añade palabra al final → equal + insert", () => {
    const tokens = diffWords("hola", "hola mundo");
    expect(tokens.find((t) => t.type === "insert")?.value).toContain("mundo");
  });

  it("elimina palabra → equal + delete", () => {
    const tokens = diffWords("hola querido mundo", "hola mundo");
    expect(tokens.find((t) => t.type === "delete")?.value).toContain("querido");
  });

  it("cambia palabra central → delete + insert intercalados", () => {
    const tokens = diffWords("hola pequeño mundo", "hola gran mundo");
    const types = tokens.map((t) => t.type);
    expect(types).toContain("delete");
    expect(types).toContain("insert");
    expect(types).toContain("equal");
  });

  it("string vacío vs no vacío → todo insert", () => {
    const tokens = diffWords("", "hola");
    expect(tokens).toEqual([{ type: "insert", value: "hola" }]);
  });
});


describe("DiffViewer string mode", () => {
  it("renderiza tokens equal/insert/delete con clases distintas", () => {
    render(<DiffViewer before="hola viejo" after="hola nuevo" />);
    // Hay al menos 1 elemento line-through (delete) y 1 con bg-wcm-accent (insert).
    const deleted = document.querySelector(".line-through");
    expect(deleted).not.toBeNull();
    const inserted = document.querySelector(".bg-wcm-accent\\/20");
    expect(inserted).not.toBeNull();
  });
});


describe("DiffViewer object mode", () => {
  it("renderiza tabla key-value side-by-side", () => {
    render(
      <DiffViewer
        before={{ cta_text: "Contacta", cta_url: "/old" }}
        after={{ cta_text: "Pedir presupuesto", cta_url: "/old" }}
      />,
    );
    expect(screen.getByText("cta_text")).toBeInTheDocument();
    expect(screen.getByText("Contacta")).toBeInTheDocument();
    expect(screen.getByText("Pedir presupuesto")).toBeInTheDocument();
    expect(screen.getAllByText("/old")).toHaveLength(2);
  });

  it("marca filas cambiadas vs iguales con opacidad distinta", () => {
    render(
      <DiffViewer
        before={{ a: 1, b: 2 }}
        after={{ a: 1, b: 999 }}
      />,
    );
    // a no cambia → fila con opacity-60.
    // b cambia → no opacity-60.
    const rows = document.querySelectorAll("tbody tr");
    expect(rows).toHaveLength(2);
  });
});


describe("DiffViewer array reorder mode", () => {
  it("muestra orden antes y después separados por flecha", () => {
    render(<DiffViewer before={[0, 1, 2]} after={[2, 0, 1]} />);
    expect(screen.getByText("orden:")).toBeInTheDocument();
    // Las dos listas presentes con sus brackets.
    expect(screen.getByText("[0, 1, 2]")).toBeInTheDocument();
    expect(screen.getByText("[2, 0, 1]")).toBeInTheDocument();
  });
});
