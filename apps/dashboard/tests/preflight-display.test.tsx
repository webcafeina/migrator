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

  it("ADR-037: plugins card pinta rojo y bloqueante si Bricks falta", () => {
    const { container } = render(
      <PreflightDisplay
        plugins={{ bricks: false, gravity_forms: true, woocommerce: true }}
      />,
    );
    // Tag "bloqueante" visible junto a Bricks Builder.
    expect(screen.getByText("bloqueante")).toBeTruthy();
    // Microcopy específico que sustituye al genérico de "residuales".
    expect(screen.getByText(/Instala Bricks Builder antes de arrancar/)).toBeTruthy();
    // El bloque tiene clase wcm-danger.
    expect(container.innerHTML).toContain("text-wcm-danger");
  });

  it("ADR-037: GF/WC faltantes pintan ámbar (no rojo) si Bricks está", () => {
    const { container } = render(
      <PreflightDisplay
        plugins={{ bricks: true, gravity_forms: false, woocommerce: false }}
      />,
    );
    // No hay tag "bloqueante" porque solo Bricks lo es y está OK.
    expect(screen.queryByText("bloqueante")).toBeNull();
    // Sigue mostrando el ámbar de plugins faltantes informativos.
    expect(container.innerHTML).toContain("text-wcm-warning");
  });

  it("loading=true muestra 'comprobando…' en lugar de 'pendiente'", () => {
    render(<PreflightDisplay loading />);
    expect(screen.getAllByText(/comprobando/).length).toBeGreaterThanOrEqual(4);
  });
});
