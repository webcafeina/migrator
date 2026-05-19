/**
 * Tests del `PreflightDisplay` (v0.18.0).
 *
 * Verifica los 3 estados visuales por chequeo (OK verde / blocking
 * rojo / warning ámbar / pendiente gris), el card de plugins con
 * conteo "presentes/total" y la lista de blocking_issues + warnings
 * agregada al pie.
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { PreflightDisplay } from "../src/app/(app)/projects/new/_components/preflight-display";

describe("PreflightDisplay", () => {
  it("renderiza estado pendiente cuando no hay datos (4 cards)", () => {
    render(<PreflightDisplay />);
    expect(screen.getAllByText("pendiente").length).toBe(4);
  });

  it("OK card verde si check.ok=true", () => {
    render(
      <PreflightDisplay
        wpTarget={{ ok: true, blocking: true, message: "WP accesible" }}
      />,
    );
    expect(screen.getByText("WP accesible")).toBeTruthy();
    expect(screen.getByText("OK")).toBeTruthy();
  });

  it("blocking rojo si check.ok=false y blocking=true", () => {
    render(
      <PreflightDisplay
        wpTarget={{ ok: false, blocking: true, message: "REST 502" }}
        blockingIssues={["WP destino: REST 502"]}
      />,
    );
    expect(screen.getByText("REST 502")).toBeTruthy();
    expect(screen.getByText("bloqueante")).toBeTruthy();
    // El bloque agregado al pie lista el blocking_issue.
    expect(screen.getByText(/Bloqueantes \(1\)/)).toBeTruthy();
  });

  it("warning ámbar si check.ok=false y blocking=false", () => {
    render(
      <PreflightDisplay
        sourceCredentials={{
          ok: false,
          blocking: false,
          message: "Wix API 401",
        }}
        warnings={["Credenciales origen: Wix API 401"]}
      />,
    );
    expect(screen.getByText("aviso")).toBeTruthy();
    expect(screen.getByText(/Avisos \(1\)/)).toBeTruthy();
  });

  it("plugins card muestra X/3 según los presentes", () => {
    render(
      <PreflightDisplay
        plugins={{ bricks: true, gravity_forms: true, woocommerce: false }}
      />,
    );
    expect(screen.getByText("2/3")).toBeTruthy();
    expect(screen.getByText(/Los plugins faltantes/)).toBeTruthy();
  });

  it("loading=true muestra 'comprobando…' en lugar de 'pendiente'", () => {
    render(<PreflightDisplay loading />);
    expect(screen.getAllByText(/comprobando/).length).toBeGreaterThanOrEqual(4);
  });
});
