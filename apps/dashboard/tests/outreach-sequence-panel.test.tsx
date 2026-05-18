/**
 * Tests del OutreachSequencePanel (v0.11.1 bug 2):
 * - Fetcha /sequences?lead_id=N en mount.
 * - Render por estado: loading, vacío, con sequence, error.
 * - Botón "Aprobar" habilitado SOLO si status=DRAFT_PENDING_REVIEW y
 *   legal_validation_passed=true.
 * - Click "Aprobar" llama POST transition con action=approve.
 *
 * NO testea el toast post-await ni el router.refresh — mismo bug
 * React 19 + happy-dom que WCM-036.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const apiGet = vi.fn();
const apiPost = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    get: (...args: unknown[]) => apiGet(...args),
    post: (...args: unknown[]) => apiPost(...args),
  },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn(), replace: vi.fn() }),
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { OutreachSequencePanel } from "../src/app/(app)/leads/_components/outreach-sequence-panel";

function _draftSeq(over: Record<string, unknown> = {}) {
  return {
    id: 1,
    lead_id: 5,
    template_name: "wix_intro_es",
    name: "Outreach inicial · Bar Pepe",
    channel: "EMAIL",
    steps_json: [
      {
        step_index: 0,
        subject: "Bar Pepe, una idea sobre vuestra web",
        body: "Hola Bar Pepe,\n\nSoy Equipo Webcafeína…",
        delay_days_from_previous: 0,
      },
      {
        step_index: 1,
        subject: "Re: vuestra web",
        body: "Hola Bar Pepe,\nTe escribía hace unos días…",
        delay_days_from_previous: 5,
      },
    ],
    status: "DRAFT_PENDING_REVIEW",
    legal_validation_passed: true,
    legal_validator_version: "v1.0",
    created_at: "2026-05-18T10:00:00Z",
    updated_at: "2026-05-18T10:00:00Z",
    ...over,
  };
}

beforeEach(() => {
  apiGet.mockReset();
  apiPost.mockReset();
});
afterEach(() => {
  vi.clearAllMocks();
});

describe("OutreachSequencePanel", () => {
  it("muestra loading mientras fetcha", () => {
    apiGet.mockReturnValue(new Promise(() => {})); // never resolves
    render(<OutreachSequencePanel leadId={5} />);
    expect(screen.getByText(/cargando borradores/i)).toBeInTheDocument();
  });

  it("muestra empty state con copy explicativa cuando no hay sequences", async () => {
    apiGet.mockResolvedValue([]);
    render(<OutreachSequencePanel leadId={5} />);
    await waitFor(() => {
      expect(screen.getByText(/sin borradores/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/componer outreach/i)).toBeInTheDocument();
  });

  it("muestra error cuando la API falla", async () => {
    apiGet.mockRejectedValue(new Error("network down"));
    render(<OutreachSequencePanel leadId={5} />);
    await waitFor(() => {
      expect(
        screen.getByText(/no se pudieron cargar los borradores/i),
      ).toBeInTheDocument();
    });
  });

  it("renderiza pasos con subject + body + delay relativo", async () => {
    apiGet.mockResolvedValue([_draftSeq()]);
    render(<OutreachSequencePanel leadId={5} />);
    await waitFor(() => {
      expect(
        screen.getByText("Bar Pepe, una idea sobre vuestra web"),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("Re: vuestra web")).toBeInTheDocument();
    // Delay 0 → "día 0"; delay 5 → "+5d desde anterior"
    expect(screen.getByText(/día 0/i)).toBeInTheDocument();
    expect(screen.getByText(/\+5d desde anterior/i)).toBeInTheDocument();
  });

  it("botón Aprobar habilitado con DRAFT_PENDING_REVIEW + validation_passed", async () => {
    apiGet.mockResolvedValue([_draftSeq()]);
    render(<OutreachSequencePanel leadId={5} />);
    const button = await screen.findByRole("button", { name: /aprobar/i });
    expect(button).toBeEnabled();
  });

  it("botón Aprobar deshabilitado si status != DRAFT_PENDING_REVIEW", async () => {
    apiGet.mockResolvedValue([_draftSeq({ status: "SENT" })]);
    render(<OutreachSequencePanel leadId={5} />);
    const button = await screen.findByRole("button", { name: /aprobar/i });
    expect(button).toBeDisabled();
  });

  it("botón Aprobar deshabilitado + warning si validación legal NO pasada", async () => {
    apiGet.mockResolvedValue([_draftSeq({ legal_validation_passed: false })]);
    render(<OutreachSequencePanel leadId={5} />);
    const button = await screen.findByRole("button", { name: /aprobar/i });
    expect(button).toBeDisabled();
    expect(
      screen.getByText(/validación legal no pasada/i),
    ).toBeInTheDocument();
  });

  it("click Aprobar llama POST /transition action=approve", async () => {
    apiGet.mockResolvedValue([_draftSeq()]);
    apiPost.mockResolvedValue({});
    const user = userEvent.setup();
    render(<OutreachSequencePanel leadId={5} />);
    const button = await screen.findByRole("button", { name: /aprobar/i });
    await user.click(button);
    expect(apiPost).toHaveBeenCalledWith(
      "/api/v1/outreach/sequences/1/transition",
      { action: "approve" },
    );
  });

  it("fetcha con searchParams.lead_id correcto", async () => {
    apiGet.mockResolvedValue([]);
    render(<OutreachSequencePanel leadId={42} />);
    await waitFor(() => {
      expect(apiGet).toHaveBeenCalledWith("/api/v1/outreach/sequences", {
        searchParams: { lead_id: 42 },
      });
    });
  });

  it("step con `delay_days` legacy (sin _from_previous) también se renderiza", async () => {
    // Sequences viejas en BD tienen `delay_days` en vez de
    // `delay_days_from_previous`. Cobertura defensiva.
    const seq = _draftSeq({
      steps_json: [
        {
          step_index: 0,
          subject: "Test",
          body: "Body",
          delay_days: 7,
        },
      ],
    });
    apiGet.mockResolvedValue([seq]);
    render(<OutreachSequencePanel leadId={5} />);
    await waitFor(() => {
      expect(screen.getByText("Test")).toBeInTheDocument();
    });
    expect(screen.getByText(/\+7d desde anterior/i)).toBeInTheDocument();
  });
});
