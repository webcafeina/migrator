/**
 * Tests del EmailPreviewIframe (v0.14.0).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const apiGet = vi.fn();

vi.mock("@/lib/api", () => ({
  api: { get: (...args: unknown[]) => apiGet(...args) },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(m: string, s: number) {
      super(m);
      this.status = s;
    }
  },
}));

import { EmailPreviewIframe } from "../src/components/email-preview-iframe";

beforeEach(() => {
  apiGet.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("EmailPreviewIframe", () => {
  it("muestra skeleton mientras carga", () => {
    apiGet.mockReturnValue(new Promise(() => {})); // never resolves
    render(<EmailPreviewIframe fetchUrl="/api/v1/templates/3/preview" />);
    expect(screen.getByText(/cargando vista previa/i)).toBeInTheDocument();
  });

  it("renderiza iframe con srcDoc cuando el fetch responde ok", async () => {
    apiGet.mockResolvedValue({
      html: "<html><body><p>Hola Bar Pepe</p></body></html>",
      subject: "Asunto demo",
    });
    render(<EmailPreviewIframe fetchUrl="/api/v1/templates/3/preview" />);
    await waitFor(() => {
      const iframe = screen.getByTitle(/vista previa del correo/i) as HTMLIFrameElement;
      expect(iframe.srcdoc).toContain("Hola Bar Pepe");
    });
    expect(screen.getByText(/asunto demo/i)).toBeInTheDocument();
  });

  it("muestra error si el fetch falla", async () => {
    apiGet.mockRejectedValue(new Error("network down"));
    render(<EmailPreviewIframe fetchUrl="/api/v1/templates/3/preview" />);
    await waitFor(() =>
      expect(screen.getByText(/vista previa no disponible/i)).toBeInTheDocument(),
    );
    expect(screen.getByText(/network down/i)).toBeInTheDocument();
  });

  it("respeta el aria-label custom", async () => {
    apiGet.mockResolvedValue({
      html: "<html><body>hola</body></html>",
      subject: null,
    });
    render(
      <EmailPreviewIframe
        fetchUrl="/api/v1/x"
        ariaLabel="Vista previa custom"
        height={300}
      />,
    );
    await waitFor(() =>
      expect(
        screen.getByLabelText(/vista previa custom/i),
      ).toBeInTheDocument(),
    );
  });
});
