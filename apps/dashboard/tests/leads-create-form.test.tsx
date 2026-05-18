/**
 * Tests del rediseño v0.11.0 — alta manual de leads:
 * - parseBulkUrls (puro, sin React)
 * - BulkPreview render por estado
 * - LeadCreateForm tabs + switch
 *
 * NO testeamos los side-effects asíncronos del submit (router.push,
 * toast tras await) — mismo bug React 19 + happy-dom + Vitest que
 * WCM-036 (ver campaigns-launch-form.test.tsx).
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn(), replace: vi.fn() }),
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

import { BulkPreview } from "../src/app/(app)/leads/new/_components/bulk-preview";
import { LeadCreateForm } from "../src/app/(app)/leads/new/lead-create-form";
import { parseBulkUrls } from "../src/app/(app)/leads/new/_components/parse-bulk-urls";

// ---------- parseBulkUrls (puro) ----------

describe("parseBulkUrls", () => {
  it("una URL por línea válida → todas en valid", () => {
    const result = parseBulkUrls("https://a.com\nhttps://b.com");
    expect(result.valid).toEqual(["https://a.com", "https://b.com"]);
    expect(result.invalid).toEqual([]);
  });

  it("autoañade https:// cuando falta protocolo", () => {
    const result = parseBulkUrls("foo.com");
    expect(result.valid).toEqual(["https://foo.com"]);
    expect(result.invalid).toEqual([]);
  });

  it("ignora líneas vacías sin contarlas como inválidas", () => {
    const result = parseBulkUrls("https://a.com\n\n\nhttps://b.com");
    expect(result.valid).toHaveLength(2);
    expect(result.invalid).toHaveLength(0);
  });

  it("ignora líneas que empiezan con # (comments)", () => {
    const result = parseBulkUrls(
      "https://a.com\n# este es un comentario\n  # también este\nhttps://b.com",
    );
    expect(result.valid).toHaveLength(2);
    expect(result.invalid).toHaveLength(0);
  });

  it("URL malformada va a invalid con número de línea 1-based", () => {
    const result = parseBulkUrls("https://a.com\nesto no es una url con espacios\nhttps://b.com");
    expect(result.valid).toHaveLength(2);
    expect(result.invalid).toHaveLength(1);
    expect(result.invalid[0]).toEqual({
      line: 2,
      raw: "esto no es una url con espacios",
    });
  });

  it("rechaza protocolos no http/https (ftp:// → invalid)", () => {
    const result = parseBulkUrls("ftp://a.com");
    expect(result.valid).toHaveLength(0);
    expect(result.invalid).toHaveLength(1);
  });

  it("entrada vacía devuelve listas vacías", () => {
    expect(parseBulkUrls("")).toEqual({ valid: [], invalid: [] });
  });
});

// ---------- BulkPreview ----------

describe("BulkPreview", () => {
  it("estado vacío muestra copy de las reglas", () => {
    render(<BulkPreview raw="" onParsed={vi.fn()} />);
    expect(screen.getByText(/pega 1 url por l[ií]nea/i)).toBeInTheDocument();
    expect(screen.getByText("#")).toBeInTheDocument();
  });

  it("contadores: 2 URLs válidas + 1 a ignorar", () => {
    const onParsed = vi.fn();
    render(
      <BulkPreview
        raw={"https://a.com\nno-url con espacios\nhttps://b.com"}
        onParsed={onParsed}
      />,
    );
    expect(screen.getByText(/2 URLs válidas/i)).toBeInTheDocument();
    expect(screen.getByText(/1 a ignorar/i)).toBeInTheDocument();
    expect(onParsed).toHaveBeenCalledWith(
      expect.objectContaining({
        valid: ["https://a.com", "https://b.com"],
      }),
    );
  });

  it("warning visible cuando > 200 URLs válidas", () => {
    const many = Array.from({ length: 201 }, (_, i) => `https://s${i}.com`).join("\n");
    render(<BulkPreview raw={many} onParsed={vi.fn()} />);
    expect(screen.getByText(/máximo 200 por lote/i)).toBeInTheDocument();
  });
});

// ---------- LeadCreateForm (tabs) ----------

describe("LeadCreateForm tabs", () => {
  it("renderiza con tab 'single' activa por defecto", () => {
    render(<LeadCreateForm />);
    const singleTab = screen.getByRole("tab", { name: /una url/i });
    const bulkTab = screen.getByRole("tab", { name: /pegar lote/i });
    expect(singleTab).toHaveAttribute("aria-selected", "true");
    expect(bulkTab).toHaveAttribute("aria-selected", "false");
    // Single tab muestra input URL
    expect(screen.getByLabelText(/^url/i)).toBeInTheDocument();
  });

  it("click en 'Pegar lote' muestra textarea", async () => {
    const user = userEvent.setup();
    render(<LeadCreateForm />);
    await user.click(screen.getByRole("tab", { name: /pegar lote/i }));
    // Ahora el panel muestra textarea bulk
    expect(screen.getByLabelText(/urls.*1 por l[ií]nea/i)).toBeInTheDocument();
  });

  it("vuelve a single tras click en 'Una URL'", async () => {
    const user = userEvent.setup();
    render(<LeadCreateForm />);
    await user.click(screen.getByRole("tab", { name: /pegar lote/i }));
    await user.click(screen.getByRole("tab", { name: /una url/i }));
    expect(screen.getByLabelText(/^url/i)).toBeInTheDocument();
  });

  it("propaga sectorSuggestions al tab single (datalist visible en DOM)", () => {
    const { container } = render(
      <LeadCreateForm sectorSuggestions={["restauración", "clínica dental"]} />,
    );
    // El datalist se renderiza con opciones — accesible vía container.
    const datalist = container.querySelector("datalist#lead-sector-suggestions");
    expect(datalist).not.toBeNull();
    expect(datalist?.querySelectorAll("option")).toHaveLength(2);
  });
});
