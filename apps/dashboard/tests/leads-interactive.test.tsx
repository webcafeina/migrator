/**
 * Tests interactivos de los componentes Client del rediseño /leads.
 *
 * Cubren la mecánica que `renderToString` no puede validar: estado local,
 * URL state via next/navigation, click handlers, atajos de teclado.
 *
 * `next/navigation` está mockeado completo — los hooks devuelven un
 * mock controlable por test (replace spy + searchParams configurable).
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { EvidenceTable } from "../src/app/(app)/leads/_components/evidence-table";
import { FilterChips } from "../src/components/filter-chips";

// ---------- Mock de next/navigation ----------

const routerReplace = vi.fn();
const routerPush = vi.fn();
const routerRefresh = vi.fn();
let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: routerReplace,
    push: routerPush,
    refresh: routerRefresh,
  }),
  useSearchParams: () => mockSearchParams,
  usePathname: () => "/leads",
}));

afterEach(() => {
  routerReplace.mockClear();
  routerPush.mockClear();
  routerRefresh.mockClear();
  mockSearchParams = new URLSearchParams();
});

// ---------- EvidenceTable ----------

describe("EvidenceTable (interactivo)", () => {
  const items = [
    {
      technology: "WordPress",
      category: "cms",
      confidence: 1.0,
      evidence: ["html:wp-content/", "meta:generator"],
    },
    {
      technology: "Elementor",
      category: "builder",
      confidence: 0.9,
      evidence: ["html:elementor-section"],
    },
  ];

  it("arranca colapsado y expande al hacer clic en el header", async () => {
    const user = userEvent.setup();
    render(<EvidenceTable items={items} />);

    // Colapsado: no se ven los datos detallados.
    expect(screen.queryByText("html:wp-content/, meta:generator")).toBeNull();
    expect(screen.getByText(/expandir/)).toBeInTheDocument();

    // Click en el toggle.
    await user.click(screen.getByRole("button", { expanded: false }));

    // Expandido: aparece la evidencia y el label cambia.
    expect(
      screen.getByText("html:wp-content/, meta:generator"),
    ).toBeInTheDocument();
    expect(screen.getByText(/colapsar/)).toBeInTheDocument();
  });

  it("re-colapsa al hacer clic una segunda vez", async () => {
    const user = userEvent.setup();
    render(<EvidenceTable items={items} defaultExpanded />);

    expect(screen.getByText(/colapsar/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { expanded: true }));
    expect(screen.getByText(/expandir/)).toBeInTheDocument();
    expect(screen.queryByText("html:elementor-section")).toBeNull();
  });

  it("usa singular `detección` cuando hay un solo item", () => {
    render(<EvidenceTable items={[items[0]!]} />);
    expect(screen.getByText("1 detección")).toBeInTheDocument();
  });
});

// ---------- FilterChips ----------

describe("FilterChips (URL state)", () => {
  const chips = [
    {
      id: "sector:marketing",
      label: "marketing",
      count: 5,
      param: "sector",
      value: "marketing",
    },
    {
      id: "builder:wordpress",
      label: "wordpress",
      count: 8,
      param: "builder",
      value: "wordpress",
    },
  ];

  it("click en chip inactivo añade el param a la URL", async () => {
    const user = userEvent.setup();
    render(<FilterChips chips={chips} />);

    await user.click(screen.getByRole("button", { name: /marketing/ }));

    expect(routerReplace).toHaveBeenCalledTimes(1);
    expect(routerReplace).toHaveBeenCalledWith("?sector=marketing", {
      scroll: false,
    });
  });

  it("click en chip activo (mismo param y valor) lo quita", async () => {
    mockSearchParams = new URLSearchParams({ builder: "wordpress" });
    const user = userEvent.setup();
    render(<FilterChips chips={chips} />);

    const chip = screen.getByRole("button", { name: /wordpress/ });
    expect(chip).toHaveAttribute("aria-pressed", "true");

    await user.click(chip);
    expect(routerReplace).toHaveBeenCalledWith("?", { scroll: false });
  });

  it("click en chip de otro valor del mismo param lo sustituye", async () => {
    mockSearchParams = new URLSearchParams({ sector: "abogacia" });
    const user = userEvent.setup();
    render(<FilterChips chips={chips} />);

    await user.click(screen.getByRole("button", { name: /marketing/ }));
    expect(routerReplace).toHaveBeenCalledWith("?sector=marketing", {
      scroll: false,
    });
  });

  it("preserva otros params (ej. `selected` del lead activo)", async () => {
    mockSearchParams = new URLSearchParams({ selected: "42" });
    const user = userEvent.setup();
    render(<FilterChips chips={chips} />);

    await user.click(screen.getByRole("button", { name: /wordpress/ }));
    // El orden no está garantizado por URLSearchParams pero ambos deben
    // aparecer.
    const [url] = routerReplace.mock.calls[0]!;
    expect(url).toContain("selected=42");
    expect(url).toContain("builder=wordpress");
  });
});

// ---------- atajos teclado (smoke con fireEvent) ----------
// El test completo del flujo de teclado vive en Playwright (e2e); aquí
// solo verificamos que el listener se enchufa sin lanzar.
describe("EvidenceTable accesibilidad teclado", () => {
  it("respeta aria-expanded según defaultExpanded inicial", () => {
    const { unmount } = render(<EvidenceTable items={[]} />);
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "false");
    unmount();
    render(<EvidenceTable items={[]} defaultExpanded />);
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "true");
  });

  it("Enter sobre el button toggle expande (sin click directo)", async () => {
    const user = userEvent.setup();
    render(<EvidenceTable items={[
      { technology: "X", category: "cms", confidence: 1, evidence: ["e1"] },
    ]} />);
    const btn = screen.getByRole("button", { expanded: false });
    btn.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByText(/colapsar/)).toBeInTheDocument();
  });
});

// ---------- fireEvent para click directo (sanity) ----------
describe("fireEvent básico funciona en happy-dom", () => {
  it("renderiza y clickea sin user-event", () => {
    const onClick = vi.fn();
    render(
      <button type="button" onClick={onClick}>
        ping
      </button>,
    );
    fireEvent.click(screen.getByRole("button", { name: "ping" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
