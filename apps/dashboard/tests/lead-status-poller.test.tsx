/**
 * Tests del polling de progreso del lead (v0.11.1 bug 1):
 * - Llama router.refresh() en intervalos mientras status indica
 *   pipeline en curso (discovered/fingerprinted).
 * - Para de hacerlo cuando status cambia a uno terminal.
 * - Devuelve null (no renderiza UI) cuando ya no hay progreso.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh, push: vi.fn(), replace: vi.fn() }),
}));

import { LeadStatusPoller } from "../src/app/(app)/leads/_components/lead-status-poller";

beforeEach(() => {
  vi.useFakeTimers();
  refresh.mockClear();
});
afterEach(() => {
  vi.useRealTimers();
});

describe("LeadStatusPoller", () => {
  it("renderiza indicador 'Fingerprint en curso…' con status=discovered", () => {
    render(<LeadStatusPoller status="discovered" intervalMs={1000} />);
    expect(screen.getByText(/fingerprint en curso/i)).toBeInTheDocument();
  });

  it("renderiza indicador 'Enriquecimiento en curso…' con status=fingerprinted", () => {
    render(<LeadStatusPoller status="fingerprinted" intervalMs={1000} />);
    expect(screen.getByText(/enriquecimiento en curso/i)).toBeInTheDocument();
  });

  it("devuelve null (sin UI) cuando status=enriched", () => {
    const { container } = render(
      <LeadStatusPoller status="enriched" intervalMs={1000} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("dispara router.refresh() cada intervalMs mientras está en curso", () => {
    render(<LeadStatusPoller status="discovered" intervalMs={1000} />);
    expect(refresh).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1000);
    expect(refresh).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(3000);
    expect(refresh).toHaveBeenCalledTimes(4);
  });

  it("no dispara router.refresh() cuando status es terminal", () => {
    render(<LeadStatusPoller status="enriched" intervalMs={500} />);
    vi.advanceTimersByTime(5000);
    expect(refresh).not.toHaveBeenCalled();
  });

  it("para el polling cuando status cambia a terminal entre renders", () => {
    const { rerender } = render(
      <LeadStatusPoller status="discovered" intervalMs={1000} />,
    );
    vi.advanceTimersByTime(2000);
    expect(refresh).toHaveBeenCalledTimes(2);
    refresh.mockClear();

    // Status cambia a enriched (pipeline terminó)
    rerender(<LeadStatusPoller status="enriched" intervalMs={1000} />);
    vi.advanceTimersByTime(5000);
    expect(refresh).not.toHaveBeenCalled();
  });
});
