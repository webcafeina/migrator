/**
 * Tests de los componentes presentacionales del Overview rediseñado:
 * - `OverviewKpiStrip` (tira de KPIs, sustituye 4 cards gigantes).
 * - `ActivityFeed` (feed agrupado por día desde audit_log).
 *
 * Renderizado server-side con `renderToString` (sin testing-library) para
 * los smoke checks; matchers jest-dom + render donde hace falta inspección
 * de árbol.
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { renderToString } from "react-dom/server";

import {
  ActivityFeed,
  type AuditLogEntry,
} from "../src/app/(app)/_overview/activity-feed";
import { OverviewKpiStrip } from "../src/app/(app)/_overview/overview-kpi-strip";

// ---------- OverviewKpiStrip ----------

describe("OverviewKpiStrip", () => {
  const kpis = [
    { label: "Leads totales", value: 29, href: "/leads" },
    { label: "Proyectos activos", value: 0, href: "/projects" },
    { label: "Errores (24h)", value: 3, href: "/errors", accent: true },
    { label: "Sin enlace", value: "—" },
  ];

  it("renderiza cada KPI con label y value", () => {
    render(<OverviewKpiStrip kpis={kpis} />);
    expect(screen.getByText("Leads totales")).toBeInTheDocument();
    expect(screen.getByText("29")).toBeInTheDocument();
    expect(screen.getByText("Proyectos activos")).toBeInTheDocument();
    expect(screen.getByText("Errores (24h)")).toBeInTheDocument();
  });

  it("envuelve en Link solo los KPIs con href", () => {
    render(<OverviewKpiStrip kpis={kpis} />);
    expect(screen.getByRole("link", { name: /leads totales/i })).toHaveAttribute(
      "href",
      "/leads",
    );
    expect(screen.getByRole("link", { name: /errores/i })).toHaveAttribute(
      "href",
      "/errors",
    );
    // "Sin enlace" no aparece como link
    expect(
      screen.queryByRole("link", { name: /sin enlace/i }),
    ).not.toBeInTheDocument();
  });

  it("aplica clase warning a valores accent=true", () => {
    const html = renderToString(<OverviewKpiStrip kpis={kpis} />);
    // El value "3" debe estar dentro de un span con la clase de warning
    expect(html).toContain("text-wcm-warning");
  });
});

// ---------- ActivityFeed: agrupación + descripciones ----------

function _entry(over: Partial<AuditLogEntry>): AuditLogEntry {
  return {
    id: Math.random().toString(36).slice(2),
    at: new Date().toISOString(),
    actor: "system",
    action: "discover",
    entity_type: "lead",
    entity_id: "1",
    payload: null,
    legal_ground: null,
    ...over,
  };
}

describe("ActivityFeed — empty state", () => {
  it("muestra mensaje cuando no hay eventos", () => {
    render(<ActivityFeed events={[]} />);
    expect(screen.getByText(/sin actividad reciente/i)).toBeInTheDocument();
    expect(
      screen.getByText(/lanza una campaña/i),
    ).toBeInTheDocument();
  });
});

describe("ActivityFeed — agrupación por día", () => {
  it("agrupa eventos del mismo día bajo un mismo encabezado", () => {
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);

    render(
      <ActivityFeed
        events={[
          _entry({ at: today.toISOString(), entity_id: "1" }),
          _entry({ at: today.toISOString(), entity_id: "2", action: "enrich" }),
          _entry({ at: yesterday.toISOString(), entity_id: "3" }),
        ]}
      />,
    );

    expect(screen.getByText("Hoy")).toBeInTheDocument();
    expect(screen.getByText("Ayer")).toBeInTheDocument();
    // El día de "Hoy" tiene 2 eventos
    expect(screen.getByText("2 eventos")).toBeInTheDocument();
    expect(screen.getByText("1 eventos")).toBeInTheDocument();
  });

  it("usa fecha corta es-ES para días anteriores a ayer", () => {
    const old = new Date();
    old.setDate(old.getDate() - 5);
    render(<ActivityFeed events={[_entry({ at: old.toISOString() })]} />);
    // No debe decir "Hoy" ni "Ayer"
    expect(screen.queryByText("Hoy")).toBeNull();
    expect(screen.queryByText("Ayer")).toBeNull();
    // Debe contener un mes abreviado en español (ene/feb/mar/.../dic)
    const html = document.body.innerHTML;
    expect(/\b(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)\b/i.test(html)).toBe(
      true,
    );
  });
});

describe("ActivityFeed — descripciones por action", () => {
  const cases: Array<[AuditLogEntry["action"], RegExp]> = [
    ["discover", /lead #42 descubierto/i],
    ["fingerprint", /lead #42 fingerprintado/i],
    ["enrich", /lead #42 enriquecido/i],
    ["send", /outreach enviado .* lead #42/i],
    ["opt_out", /lead #42 marcado opt-out/i],
    ["create", /lead #42 creado/i],
    ["update", /lead #42 actualizado/i],
    ["delete", /lead #42 eliminado/i],
    ["deploy", /lead #42 desplegado/i],
  ];

  for (const [action, pattern] of cases) {
    it(`describe la acción "${action}" en castellano`, () => {
      render(
        <ActivityFeed
          events={[_entry({ action, entity_id: "42", entity_type: "lead" })]}
        />,
      );
      expect(screen.getByText(pattern)).toBeInTheDocument();
    });
  }

  it("usa label en español para el entity_type (project → Proyecto)", () => {
    render(
      <ActivityFeed
        events={[
          _entry({ action: "deploy", entity_type: "project", entity_id: "7" }),
        ]}
      />,
    );
    expect(screen.getByText(/proyecto #7 desplegado/i)).toBeInTheDocument();
  });

  it("incluye payload.url como detalle en discover si está presente", () => {
    render(
      <ActivityFeed
        events={[
          _entry({
            action: "discover",
            payload: { url: "https://barpepe.es" },
          }),
        ]}
      />,
    );
    expect(screen.getByText(/barpepe\.es/)).toBeInTheDocument();
  });

  it("system event sin entity usa el payload.message", () => {
    render(
      <ActivityFeed
        events={[
          _entry({
            action: "system",
            entity_type: null,
            entity_id: null,
            payload: { message: "Retention sweep ejecutado" },
          }),
        ]}
      />,
    );
    expect(screen.getByText(/retention sweep/i)).toBeInTheDocument();
  });
});

describe("ActivityFeed — links por entity", () => {
  it("lead enlaza a /leads?selected={id}", () => {
    render(
      <ActivityFeed
        events={[
          _entry({ entity_type: "lead", entity_id: "42", action: "enrich" }),
        ]}
      />,
    );
    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      "/leads?selected=42",
    );
  });

  it("project enlaza a /projects/{id}", () => {
    render(
      <ActivityFeed
        events={[
          _entry({
            entity_type: "project",
            entity_id: "7",
            action: "deploy",
          }),
        ]}
      />,
    );
    expect(screen.getByRole("link")).toHaveAttribute("href", "/projects/7");
  });

  it("entity desconocida no enlaza", () => {
    render(
      <ActivityFeed
        events={[
          _entry({
            entity_type: "unknown_thing",
            entity_id: "x",
            action: "create",
          }),
        ]}
      />,
    );
    expect(screen.queryByRole("link")).toBeNull();
  });
});
