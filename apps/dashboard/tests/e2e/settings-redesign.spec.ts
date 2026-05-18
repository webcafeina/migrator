/**
 * E2E del rediseño /settings (bloques 1-4 v1.0.0). Cierra el rediseño
 * visual completo del dashboard — 11 pantallas en el nuevo lenguaje.
 *
 * Mismo patrón que las specs anteriores: tests client-side puros
 * ejecutables (header castellano "Ajustes", subtítulo descriptivo);
 * tests que verifican contenido del Server Component (usuario,
 * runtime, health rows) → `test.skip(SSR_BLOCKED, "WCM-021")`.
 *
 * Una guardia explícita: NO debe aparecer la mentira "Fase 14" en
 * ningún sitio del DOM — equivalente a la guardia "Fase 10" en
 * projects-detail-redesign.spec.ts (v0.8.0).
 */

import { expect, test } from "@playwright/test";

import { installBaseMocks, loginViaCookie } from "./fixtures/api-mocks";

/** Flip a false cuando WCM-021 (MSW node) esté implementado. */
const SSR_BLOCKED = true;

test.describe("/settings — rediseño", () => {
  test.beforeEach(async ({ page }) => {
    await installBaseMocks(page);
    await loginViaCookie(page);
  });

  test("header con título 'Ajustes' en castellano y subtítulo descriptivo", async ({
    page,
  }) => {
    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: /^ajustes$/i })).toBeVisible();
    await expect(
      page.getByText(/usuario actual.*estado del api.*procedimientos operativos/i),
    ).toBeVisible();
  });

  test("3 secciones con sus headers visibles", async ({ page }) => {
    await page.goto("/settings");
    await expect(page.getByText(/usuario actual/i).first()).toBeVisible();
    await expect(page.getByText(/estado del sistema/i)).toBeVisible();
    await expect(page.getByText(/operación/i).first()).toBeVisible();
  });

  test("NO menciona la mentira eliminada 'Fase 14'", async ({ page }) => {
    // Guardia análoga al test "Fase 10" de projects-detail-redesign:
    // si vuelve a aparecer (ej. nueva copy descuidada), este test falla.
    await page.goto("/settings");
    await expect(page.getByText(/fase\s*14/i)).toHaveCount(0);
  });

  test("UserCard muestra email + rol del usuario logueado", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021: /auth/me lo fetcha el Server Component");
    await page.goto("/settings");
    await expect(page.getByText("ops@webcafeina.com")).toBeVisible();
    await expect(page.getByText(/operator|admin/i)).toBeVisible();
  });

  test("SystemInfoPanel muestra version + entorno + alembic + uptime", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021: /system/info lo fetcha el Server Component");
    await page.goto("/settings");
    await expect(page.getByText("1.0.0")).toBeVisible();
    await expect(page.getByText(/test|development|production/i)).toBeVisible();
    await expect(page.getByText("c8e1dc21716b")).toBeVisible();
    // uptime formateado
    await expect(page.getByText(/\d+[smhd]/)).toBeVisible();
  });

  test("3 health rows (postgres, redis, r2) con sus status", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto("/settings");
    await expect(page.getByText("postgres")).toBeVisible();
    await expect(page.getByText("redis")).toBeVisible();
    await expect(page.getByText("r2")).toBeVisible();
    // r2 skipped por defecto en el fixture → '(opcional)' visible
    await expect(page.getByText("(opcional)")).toBeVisible();
  });

  test("OperationRunbook incluye SSH y comandos wcm users", async ({
    page,
  }) => {
    await page.goto("/settings");
    await expect(
      page.getByText(/ssh root@migrator\.webcafeina\.com/i),
    ).toBeVisible();
    await expect(
      page.getByText(/systemctl restart webcafeina-api/i),
    ).toBeVisible();
    await expect(page.getByText(/wcm users list/i)).toBeVisible();
  });
});
