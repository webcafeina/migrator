/**
 * Tests de los 3 componentes del rediseño /settings v1.0.0:
 * - UserCard
 * - SystemInfoPanel
 * - OperationRunbook
 *
 * Cubren render por estado (con/sin datos), badges por rol/env/overall,
 * formato de uptime, y que el runbook NO contiene la mentira eliminada
 * ("Fase 14") ni placeholders ambiguos.
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { OperationRunbook } from "../src/app/(app)/settings/_components/operation-runbook";
import {
  SystemInfoPanel,
  type SystemInfoData,
} from "../src/app/(app)/settings/_components/system-info-panel";
import { UserCard } from "../src/app/(app)/settings/_components/user-card";
import type { UserRead } from "@/types/api";

// ---------- UserCard ----------

function _user(over: Partial<UserRead> = {}): UserRead {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    email: "ops@webcafeina.com",
    name: "Operadora",
    role: "operator",
    is_active: true,
    created_at: "2026-05-14T12:00:00Z",
    updated_at: "2026-05-14T12:00:00Z",
    ...over,
  } as UserRead;
}

describe("UserCard", () => {
  it("renderiza email, nombre, id y badge de rol", () => {
    render(<UserCard user={_user()} />);
    expect(screen.getByText("ops@webcafeina.com")).toBeInTheDocument();
    expect(screen.getByText("Operadora")).toBeInTheDocument();
    expect(screen.getByText("operator")).toBeInTheDocument();
    expect(
      screen.getByText("00000000-0000-0000-0000-000000000001"),
    ).toBeInTheDocument();
  });

  it("rol admin se resalta con acento lima", () => {
    render(<UserCard user={_user({ role: "admin" })} />);
    const badge = screen.getByText("admin");
    expect(badge.className).toContain("wcm-accent");
  });

  it("muestra error explicativo cuando user es null", () => {
    render(<UserCard user={null} />);
    expect(
      screen.getByText(/no se pudo recuperar el usuario/i),
    ).toBeInTheDocument();
  });
});

// ---------- SystemInfoPanel ----------

function _info(over: Partial<SystemInfoData> = {}): SystemInfoData {
  return {
    version: "1.0.0",
    environment: "development",
    python_version: "3.14.0",
    alembic_revision: "c8e1dc21716b",
    uptime_seconds: 3725,
    health: { overall: "ok", db: "ok", redis: "ok", r2: "skipped" },
    ...over,
  };
}

describe("SystemInfoPanel", () => {
  it("renderiza versión, environment, python y revision", () => {
    render(<SystemInfoPanel info={_info()} />);
    expect(screen.getByText("1.0.0")).toBeInTheDocument();
    expect(screen.getByText("development")).toBeInTheDocument();
    expect(screen.getByText("3.14.0")).toBeInTheDocument();
    expect(screen.getByText("c8e1dc21716b")).toBeInTheDocument();
  });

  it("formatea uptime: < 60s, segundos; < 1h, minutos; < 1d, h+m; ≥ 1d, d+h+m", () => {
    const { rerender } = render(<SystemInfoPanel info={_info({ uptime_seconds: 30 })} />);
    expect(screen.getByText("30s")).toBeInTheDocument();
    rerender(<SystemInfoPanel info={_info({ uptime_seconds: 300 })} />);
    expect(screen.getByText("5m")).toBeInTheDocument();
    rerender(<SystemInfoPanel info={_info({ uptime_seconds: 3725 })} />);
    expect(screen.getByText("1h 2m")).toBeInTheDocument();
    rerender(<SystemInfoPanel info={_info({ uptime_seconds: 90061 })} />);
    expect(screen.getByText("1d 1h 1m")).toBeInTheDocument();
  });

  it("environment 'production' badge en ámbar", () => {
    render(<SystemInfoPanel info={_info({ environment: "production" })} />);
    const badge = screen.getByText("production");
    expect(badge.className).toContain("wcm-warning");
  });

  it("alembic null muestra texto 'sin migraciones aplicadas'", () => {
    render(<SystemInfoPanel info={_info({ alembic_revision: null })} />);
    expect(screen.getByText(/sin migraciones aplicadas/i)).toBeInTheDocument();
  });

  it("3 health rows con dot + label + status", () => {
    render(<SystemInfoPanel info={_info()} />);
    expect(screen.getByText("postgres")).toBeInTheDocument();
    expect(screen.getByText("redis")).toBeInTheDocument();
    expect(screen.getByText("r2")).toBeInTheDocument();
    // r2 skipped lleva nota '(opcional)'
    expect(screen.getByText("(opcional)")).toBeInTheDocument();
  });

  it("overall=fail muestra badge danger; overall=degraded muestra warning", () => {
    const { rerender } = render(
      <SystemInfoPanel
        info={_info({ health: { overall: "fail", db: "fail", redis: "ok", r2: "skipped" } })}
      />,
    );
    // 'fail' aparece 2 veces (overall + db). Cualquiera debe llevar
    // las clases de danger para validar el mapeo de color.
    const fails = screen.getAllByText("fail");
    expect(fails.length).toBe(2);
    expect(fails.every((el) => el.className.includes("wcm-danger"))).toBe(true);

    rerender(
      <SystemInfoPanel
        info={_info({ health: { overall: "degraded", db: "ok", redis: "ok", r2: "fail" } })}
      />,
    );
    expect(screen.getByText("degraded").className).toContain("wcm-warning");
  });

  it("muestra error explicativo cuando info es null", () => {
    render(<SystemInfoPanel info={null} />);
    expect(screen.getByText(/api no responde/i)).toBeInTheDocument();
    expect(
      screen.getByText(/systemctl status webcafeina-api/i),
    ).toBeInTheDocument();
  });
});

// ---------- OperationRunbook ----------

describe("OperationRunbook", () => {
  it("renderiza las 2 secciones con sus comandos", () => {
    render(<OperationRunbook />);
    expect(
      screen.getByText(/editar variables del sistema/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/gestionar usuarios/i)).toBeInTheDocument();
    expect(
      screen.getByText(/ssh root@migrator\.webcafeina\.com/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/systemctl restart webcafeina-api/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/wcm users list/i)).toBeInTheDocument();
  });

  it("NO contiene la mentira eliminada 'Fase 14'", () => {
    const { container } = render(<OperationRunbook />);
    expect(container.textContent ?? "").not.toMatch(/fase\s*14/i);
  });

  it("incluye link a /admin/users (UI ahora real, no vaporware)", () => {
    const { container } = render(<OperationRunbook />);
    const link = container.querySelector("a[href='/admin/users']");
    expect(link).not.toBeNull();
  });
});
