/**
 * Smoke tests de los componentes presentacionales del rediseño /leads.
 *
 * Verifican que cada componente renderiza sin lanzar y produce el dato
 * pivote esperado en el HTML. La interactividad (toggle EvidenceTable,
 * click FilterChips) se cubre en bloque 5 con @testing-library/react.
 */

import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";

import { ActivityTimeline } from "../src/app/(app)/leads/_components/activity-timeline";
import { EvidenceTable } from "../src/app/(app)/leads/_components/evidence-table";
import { FingerprintList } from "../src/app/(app)/leads/_components/fingerprint-list";
import { ScorePanel } from "../src/app/(app)/leads/_components/score-panel";
import { TopbarStats } from "../src/app/(app)/leads/_components/topbar-stats";

describe("ScorePanel", () => {
  it("renderiza la cifra del score y la barra al porcentaje correcto", () => {
    const html = renderToString(
      <ScorePanel score={88} percentile={92} sectorMedian={51} sectorName="marketing" />,
    );
    expect(html).toContain("88");
    expect(html).toContain("p92");
    expect(html).toContain("marketing");
    // barra de fill al 88%
    expect(html).toMatch(/width:\s*88%/);
    // tick mediana al 51%
    expect(html).toMatch(/left:\s*51%/);
  });

  it("omite líneas de contexto si no hay percentile ni median", () => {
    const html = renderToString(<ScorePanel score={42} />);
    expect(html).toContain("42");
    expect(html).not.toContain("respecto a mediana");
    expect(html).not.toMatch(/\bp\d+\b/);
  });

  it("clampa el score al rango 0..100", () => {
    const overflow = renderToString(<ScorePanel score={150} />);
    expect(overflow).not.toContain("150");
    expect(overflow).toMatch(/width:\s*100%/);
    const underflow = renderToString(<ScorePanel score={-10} />);
    expect(underflow).not.toContain("-10");
    expect(underflow).toMatch(/width:\s*0%/);
  });
});

describe("FingerprintList", () => {
  it("renderiza cada item con su confianza", () => {
    const html = renderToString(
      <FingerprintList
        items={[
          { technology: "WordPress", category: "cms", confidence: 1.0 },
          { technology: "Elementor", category: "builder", confidence: 0.9 },
        ]}
      />,
    );
    expect(html).toContain("WordPress");
    expect(html).toContain("Elementor");
    expect(html).toContain("cms");
    expect(html).toContain("1.00");
    expect(html).toContain("0.90");
  });

  it("muestra mensaje muted con lista vacía", () => {
    const html = renderToString(<FingerprintList items={[]} />);
    expect(html).toContain("Sin detecciones registradas");
  });
});

describe("EvidenceTable", () => {
  it("renderiza colapsada por defecto mostrando solo el count", () => {
    const html = renderToString(
      <EvidenceTable
        items={[
          {
            technology: "WordPress",
            category: "cms",
            confidence: 1.0,
            evidence: ["html:wp-content/"],
          },
          {
            technology: "Elementor",
            category: "builder",
            confidence: 0.9,
            evidence: ["html:elementor-section"],
          },
        ]}
      />,
    );
    expect(html).toContain("2 detecciones");
    expect(html).toContain("expandir");
    // colapsada: el detalle de evidencia NO está en el HTML inicial
    expect(html).not.toContain("html:wp-content/");
  });

  it("respeta defaultExpanded=true", () => {
    const html = renderToString(
      <EvidenceTable
        defaultExpanded
        items={[
          {
            technology: "WordPress",
            category: "cms",
            confidence: 1.0,
            evidence: ["meta:generator"],
          },
        ]}
      />,
    );
    expect(html).toContain("meta:generator");
    expect(html).toContain("colapsar");
  });
});

describe("ActivityTimeline", () => {
  it("renderiza cada evento con when, what y why", () => {
    const html = renderToString(
      <ActivityTimeline
        events={[
          {
            when: "hace 3d",
            what: "enriquecido",
            why: "2 emails · 3 teléfonos",
            highlight: true,
          },
          {
            when: "hace 3d",
            what: "descubierto",
            why: "campaña marketing/Cáceres",
          },
        ]}
      />,
    );
    expect(html).toContain("enriquecido");
    expect(html).toContain("descubierto");
    expect(html).toContain("2 emails");
    expect(html).toContain("hace 3d");
  });

  it("muestra empty state si no hay eventos", () => {
    const html = renderToString(<ActivityTimeline events={[]} />);
    expect(html).toContain("Sin actividad registrada");
  });
});

describe("TopbarStats", () => {
  it("renderiza los 4 stats con separadores", () => {
    const html = renderToString(
      <TopbarStats
        stats={{
          total: 29,
          uncontacted: 12,
          avgScore: 41.3,
          distinctBuilders: 5,
        }}
      />,
    );
    expect(html).toContain("29");
    expect(html).toContain("12");
    expect(html).toContain("41"); // round(41.3)
    expect(html).toContain("5");
    expect(html).toContain("leads");
    expect(html).toContain("sin contactar");
    expect(html).toContain("builders");
  });

  it("muestra '—' en score medio si avgScore es null", () => {
    const html = renderToString(
      <TopbarStats
        stats={{ total: 0, uncontacted: 0, avgScore: null, distinctBuilders: 0 }}
      />,
    );
    expect(html).toContain("—");
  });

  it("renderiza dot de worker si se proporciona health", () => {
    const html = renderToString(
      <TopbarStats
        stats={{ total: 1, uncontacted: 0, avgScore: 50, distinctBuilders: 1 }}
        worker={{ status: "ok", lastSeenLabel: "hace 12 min" }}
      />,
    );
    expect(html).toContain("worker");
    expect(html).toContain("hace 12 min");
  });
});
