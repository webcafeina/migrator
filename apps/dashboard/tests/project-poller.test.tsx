/**
 * Tests del `ProjectPoller` v0.19.0 (SSE + fallback polling).
 *
 * Cubre: no renderiza si status terminal, banner visible si running,
 * intenta EventSource y refresca al recibir mensaje, fallback al
 * polling cuando EventSource entra en CLOSED.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";

import { ProjectPoller } from "../src/app/(app)/projects/[id]/_components/project-poller";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh, push: vi.fn() }),
}));

class FakeEventSource {
  url: string;
  readyState: number = 0; // CONNECTING
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  closed = false;
  static CLOSED = 2;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  close() {
    this.closed = true;
    this.readyState = FakeEventSource.CLOSED;
  }

  static instances: FakeEventSource[] = [];
  static reset() {
    FakeEventSource.instances = [];
  }
}

beforeEach(() => {
  refresh.mockReset();
  FakeEventSource.reset();
  vi.useFakeTimers();
  (globalThis as unknown as { EventSource: typeof FakeEventSource }).EventSource =
    FakeEventSource;
});

afterEach(() => {
  vi.useRealTimers();
});

describe("ProjectPoller (v0.19.0)", () => {
  it("NO renderiza si status terminal (completed)", () => {
    const { container } = render(
      <ProjectPoller status="completed" projectId={7} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renderiza banner y abre EventSource si status=running", () => {
    render(<ProjectPoller status="running" projectId={7} />);
    expect(screen.getByRole("status")).toBeTruthy();
    expect(FakeEventSource.instances.length).toBe(1);
    expect(FakeEventSource.instances[0]!.url).toBe(
      "/api/v1/projects/7/events",
    );
  });

  it("router.refresh se llama al recibir un mensaje SSE", () => {
    render(<ProjectPoller status="running" projectId={7} />);
    const es = FakeEventSource.instances[0]!;
    act(() => {
      es.onopen?.(new Event("open"));
      es.onmessage?.(new MessageEvent("message", { data: "{}" }));
    });
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("modo cambia a 'sse' tras onopen", () => {
    render(<ProjectPoller status="running" projectId={7} />);
    const es = FakeEventSource.instances[0]!;
    act(() => {
      es.onopen?.(new Event("open"));
    });
    const banner = screen.getByRole("status");
    expect(banner.getAttribute("data-mode")).toBe("sse");
    expect(banner.textContent).toContain("stream SSE");
  });

  it("fallback a polling cuando EventSource entra en CLOSED", () => {
    render(
      <ProjectPoller
        status="running"
        projectId={7}
        fallbackIntervalMs={2000}
      />,
    );
    const es = FakeEventSource.instances[0]!;
    act(() => {
      es.close(); // CLOSED
      es.onerror?.(new Event("error"));
    });
    const banner = screen.getByRole("status");
    expect(banner.getAttribute("data-mode")).toBe("polling");
    expect(banner.textContent).toContain("polling 2s");
    expect(es.closed).toBe(true);
  });
});
