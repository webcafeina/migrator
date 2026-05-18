/**
 * Tests del FirmaCard (v0.12.0 bloque 5).
 *
 * Read-only en /settings con datos legales del composer. Warning rojo
 * si COMPANY_CIF o COMPANY_ADDRESS faltan en env.
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import {
  FirmaCard,
  type FirmaData,
} from "../src/app/(app)/settings/_components/firma-card";

function _firma(over: Partial<FirmaData> = {}): FirmaData {
  return {
    company_legal_name: "Webcafeína S.L.",
    company_cif: "B10463990",
    company_address: "Santa Cristina s/n – Edificio Embarcadero, 10195 Cáceres",
    company_contact_email: "info@webcafeina.com",
    company_privacy_policy_url: "https://webcafeina.com/politica-de-privacidad",
    opt_out_url_base: "https://migrator.webcafeina.com/opt-out",
    ...over,
  };
}

describe("FirmaCard", () => {
  it("renderiza los 6 campos cuando la firma está completa", () => {
    render(<FirmaCard firma={_firma()} />);
    expect(screen.getByText("Webcafeína S.L.")).toBeInTheDocument();
    expect(screen.getByText("B10463990")).toBeInTheDocument();
    expect(
      screen.getByText(/santa cristina.*cáceres/i),
    ).toBeInTheDocument();
    expect(screen.getByText("info@webcafeina.com")).toBeInTheDocument();
    expect(
      screen.getByText("https://webcafeina.com/politica-de-privacidad"),
    ).toBeInTheDocument();
  });

  it("warning rojo + texto 'falta COMPANY_CIF' cuando cif=null", () => {
    render(<FirmaCard firma={_firma({ company_cif: null })} />);
    const warning = screen.getByText(/falta COMPANY_CIF/);
    expect(warning).toBeInTheDocument();
    expect(warning.className).toContain("wcm-danger");
  });

  it("warning rojo cuando address=null", () => {
    render(<FirmaCard firma={_firma({ company_address: null })} />);
    expect(screen.getByText(/falta COMPANY_ADDRESS/)).toBeInTheDocument();
  });

  it("error inline cuando firma es null (API caído)", () => {
    render(<FirmaCard firma={null} />);
    expect(
      screen.getByText(/no se pudo recuperar la firma legal/i),
    ).toBeInTheDocument();
  });

  it("microcopy de SSH para editar visible", () => {
    render(<FirmaCard firma={_firma()} />);
    expect(
      screen.getByText(/SSH al servidor/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/systemctl restart/i)).toBeInTheDocument();
  });
});
