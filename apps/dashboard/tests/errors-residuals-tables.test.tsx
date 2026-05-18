/**
 * Tests de las 2 tablas del rediseño v0.9.0:
 * - `ErrorsTable`
 * - `ResidualTasksTable`
 *
 * Cubren render por fila, badges por severity/category/status,
 * link a /projects/{id}, empty state delegado al padre, MarkDone
 * solo en tareas abiertas (mockeo trivial — la acción interactiva
 * vive en mark-done-button con su propio test).
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// MarkDoneButton se mockea para evitar fetch real / sonner / router.
vi.mock("../src/app/(app)/residual-tasks/mark-done-button", () => ({
  MarkDoneButton: ({ taskId }: { taskId: number }) => (
    <button type="button" data-testid={`done-${taskId}`}>Done</button>
  ),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn(), replace: vi.fn() }),
}));

import { ErrorsTable } from "../src/app/(app)/errors/_components/errors-table";
import { ResidualTasksTable } from "../src/app/(app)/residual-tasks/_components/residual-tasks-table";
import type { ErrorLogRead, ResidualTaskRead } from "@/types/api";

afterEach(() => {
  vi.clearAllMocks();
});

// ---------- ErrorsTable ----------

function _error(over: Partial<ErrorLogRead> = {}): ErrorLogRead {
  return {
    id: crypto.randomUUID(),
    at: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    severity: "error",
    component: "wcm_worker.agents.prospector",
    message: "Rate limit hit on Google Places",
    project_id: null,
    stack: null,
    context_json: null,
    sentry_event_id: null,
    notified_at: null,
    ...over,
  } as ErrorLogRead;
}

describe("ErrorsTable", () => {
  it("renderiza una fila por entrada con componente + mensaje", () => {
    render(<ErrorsTable errors={[_error(), _error({ message: "Otro" })]} />);
    expect(
      screen.getByText("Rate limit hit on Google Places"),
    ).toBeInTheDocument();
    expect(screen.getByText("Otro")).toBeInTheDocument();
  });

  it("muestra 5 severities en castellano con colores diferenciados", () => {
    render(
      <ErrorsTable
        errors={[
          _error({ severity: "critical" }),
          _error({ severity: "error" }),
          _error({ severity: "warning" }),
          _error({ severity: "info" }),
          _error({ severity: "debug" }),
        ]}
      />,
    );
    expect(screen.getByText("crítico")).toBeInTheDocument();
    expect(screen.getByText("error")).toBeInTheDocument();
    expect(screen.getByText("warning")).toBeInTheDocument();
    expect(screen.getByText("info")).toBeInTheDocument();
    expect(screen.getByText("debug")).toBeInTheDocument();
  });

  it("enlaza al proyecto cuando project_id existe", () => {
    render(<ErrorsTable errors={[_error({ project_id: 7 })]} />);
    expect(
      screen.getByRole("link", { name: "#7" }),
    ).toHaveAttribute("href", "/projects/7");
  });

  it("muestra '—' cuando project_id es null", () => {
    render(<ErrorsTable errors={[_error({ project_id: null })]} />);
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("devuelve null con lista vacía (empty al padre)", () => {
    const { container } = render(<ErrorsTable errors={[]} />);
    expect(container.firstChild).toBeNull();
  });
});

// ---------- ResidualTasksTable ----------

function _task(over: Partial<ResidualTaskRead> = {}): ResidualTaskRead {
  return {
    id: 1,
    project_id: 1,
    title: "Mover DNS",
    description: "Cambiar A/CNAME al WHM destino.",
    category: "blocking_go_live",
    status: "open",
    estimated_minutes: 30,
    assignee_hint: "operador",
    generated_by: "checklist-generator",
    closed_at: null,
    created_at: "2026-05-15T10:00:00Z",
    updated_at: "2026-05-15T10:00:00Z",
    ...over,
  } as ResidualTaskRead;
}

describe("ResidualTasksTable", () => {
  it("renderiza una fila por tarea con título y descripción", () => {
    render(
      <ResidualTasksTable
        tasks={[_task(), _task({ id: 2, title: "Otra", description: "Y" })]}
      />,
    );
    expect(screen.getByText("Mover DNS")).toBeInTheDocument();
    expect(screen.getByText("Otra")).toBeInTheDocument();
  });

  it("categoría blocking_go_live muestra etiqueta 'bloqueante' en ámbar", () => {
    render(<ResidualTasksTable tasks={[_task({ category: "blocking_go_live" })]} />);
    const badge = screen.getByText("bloqueante");
    expect(badge.className).toContain("wcm-warning");
  });

  it("link al proyecto en cada fila", () => {
    render(<ResidualTasksTable tasks={[_task({ project_id: 42 })]} />);
    expect(
      screen.getByRole("link", { name: "#42" }),
    ).toHaveAttribute("href", "/projects/42");
  });

  it("muestra MarkDoneButton solo en tareas no cerradas", () => {
    render(
      <ResidualTasksTable
        tasks={[
          _task({ id: 1, status: "open" }),
          _task({ id: 2, status: "in_progress" }),
          _task({ id: 3, status: "done" }),
          _task({ id: 4, status: "skipped" }),
        ]}
      />,
    );
    expect(screen.getByTestId("done-1")).toBeInTheDocument();
    expect(screen.getByTestId("done-2")).toBeInTheDocument();
    expect(screen.queryByTestId("done-3")).toBeNull();
    expect(screen.queryByTestId("done-4")).toBeNull();
  });

  it("5 status pills castellanas", () => {
    render(
      <ResidualTasksTable
        tasks={[
          _task({ id: 1, status: "open" }),
          _task({ id: 2, status: "in_progress" }),
          _task({ id: 3, status: "blocked" }),
          _task({ id: 4, status: "done" }),
          _task({ id: 5, status: "skipped" }),
        ]}
      />,
    );
    expect(screen.getByText("abierta")).toBeInTheDocument();
    expect(screen.getByText("en curso")).toBeInTheDocument();
    expect(screen.getByText("bloqueada")).toBeInTheDocument();
    expect(screen.getByText("cerrada")).toBeInTheDocument();
    expect(screen.getByText("omitida")).toBeInTheDocument();
  });

  it("devuelve null con lista vacía", () => {
    const { container } = render(<ResidualTasksTable tasks={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
