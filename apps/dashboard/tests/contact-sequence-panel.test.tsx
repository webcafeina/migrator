/**
 * Tests del ContactSequencePanel (v0.11.1 bug 2):
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

import { ContactSequencePanel } from "../src/app/(app)/leads/_components/contact-sequence-panel";

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

describe("ContactSequencePanel", () => {
  it("muestra loading mientras fetcha", () => {
    apiGet.mockReturnValue(new Promise(() => {})); // never resolves
    render(<ContactSequencePanel leadId={5} />);
    expect(screen.getByText(/cargando borradores/i)).toBeInTheDocument();
  });

  it("muestra empty state con copy explicativa cuando no hay sequences", async () => {
    apiGet.mockResolvedValue([]);
    render(<ContactSequencePanel leadId={5} />);
    await waitFor(() => {
      expect(screen.getByText(/sin borradores/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/componer contacto/i)).toBeInTheDocument();
  });

  it("muestra error cuando la API falla", async () => {
    apiGet.mockRejectedValue(new Error("network down"));
    render(<ContactSequencePanel leadId={5} />);
    await waitFor(() => {
      expect(
        screen.getByText(/no se pudieron cargar los borradores/i),
      ).toBeInTheDocument();
    });
  });

  it("renderiza pasos con subject + body + delay relativo", async () => {
    apiGet.mockResolvedValue([_draftSeq()]);
    render(<ContactSequencePanel leadId={5} />);
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
    render(<ContactSequencePanel leadId={5} />);
    const button = await screen.findByRole("button", { name: /aprobar/i });
    expect(button).toBeEnabled();
  });

  it("status lowercase del API se normaliza — Aprobar y Editar funcionan (regresión bug v0.12.0)", async () => {
    // El API serializa los enums lowercase ('draft_pending_review').
    // El bug original (v0.12.0 pre-fix) comparaba con UPPERCASE y
    // dejaba Aprobar disabled + botón Editar oculto. Test cubre ambos.
    apiGet.mockResolvedValue([_draftSeq({ status: "draft_pending_review" })]);
    render(<ContactSequencePanel leadId={5} />);
    const approve = await screen.findByRole("button", { name: /aprobar/i });
    expect(approve).toBeEnabled();
    // Botones Editar visibles en cada paso (editable=true).
    const editButtons = screen.getAllByRole("button", { name: /^editar$/i });
    expect(editButtons.length).toBe(2); // 2 pasos del _draftSeq
  });

  it("botón Aprobar NO se renderiza si status no permite aprobar", async () => {
    // status=completed → no acciones; el botón Aprobar no aparece.
    apiGet.mockResolvedValue([_draftSeq({ status: "completed" })]);
    render(<ContactSequencePanel leadId={5} />);
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: /aprobar/i })).toBeNull();
    });
    expect(
      screen.getByText(/sin acciones disponibles/i),
    ).toBeInTheDocument();
  });

  it("botón Aprobar deshabilitado + warning si validación legal NO pasada", async () => {
    apiGet.mockResolvedValue([_draftSeq({ legal_validation_passed: false })]);
    render(<ContactSequencePanel leadId={5} />);
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
    render(<ContactSequencePanel leadId={5} />);
    const button = await screen.findByRole("button", { name: /aprobar/i });
    await user.click(button);
    expect(apiPost).toHaveBeenCalledWith(
      "/api/v1/outreach/sequences/1/transition",
      { action: "approve" },
    );
  });

  it("fetcha con searchParams.lead_id correcto", async () => {
    apiGet.mockResolvedValue([]);
    render(<ContactSequencePanel leadId={42} />);
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
    render(<ContactSequencePanel leadId={5} />);
    await waitFor(() => {
      expect(screen.getByText("Test")).toBeInTheDocument();
    });
    expect(screen.getByText(/\+7d desde anterior/i)).toBeInTheDocument();
  });
});
