/**
 * E2E del rediseño /campaigns (bloques 1-4).
 *
 * Mismo patrón que /leads y /: tests client-side puros ejecutables,
 * tests que verifican contenido del Server Component → `test.skip(SSR_BLOCKED)`.
 */

import { expect, test } from "@playwright/test";

import { installBaseMocks, loginViaCookie } from "./fixtures/api-mocks";

/** Flip a false cuando WCM-021 (MSW node) esté implementado. */
const SSR_BLOCKED = true;

test.describe("/campaigns — rediseño 3-zona", () => {
  test.beforeEach(async ({ page }) => {
    await installBaseMocks(page);
    await loginViaCookie(page);
  });

  test("header con título 'Campañas de prospección'", async ({ page }) => {
    await page.goto("/campaigns");
    await expect(
      page.getByRole("heading", { name: /campañas de prospección/i }),
    ).toBeVisible();
  });

  test("form compacto muestra los 3 inputs + botón", async ({ page }) => {
    await page.goto("/campaigns");
    await expect(page.getByLabel(/sector/i)).toBeVisible();
    await expect(page.getByLabel(/región/i)).toBeVisible();
    await expect(page.getByLabel(/objetivo/i)).toBeVisible();
    await expect(
      page.getByRole("button", { name: /lanzar campaña/i }),
    ).toBeVisible();
  });

  test("microcopy legal con 'nunca' visible bajo el form", async ({ page }) => {
    await page.goto("/campaigns");
    await expect(
      page.getByText(/el sistema\s+nunca\s+envía outreach/i),
    ).toBeVisible();
  });

  test("la nota técnica obsoleta de ProspectorAgent NO aparece (fix P0)", async ({
    page,
  }) => {
    // Mentira desde v0.2.0 — bug de copy detectado en auditoría visual.
    await page.goto("/campaigns");
    const obsolete = page.getByText(/ProspectorAgent\s+está\s+actualmente\s+en\s+stub/i);
    await expect(obsolete).toHaveCount(0);
    const fase9 = page.getByText(/llega en Fase 9/i);
    await expect(fase9).toHaveCount(0);
  });

  test("target arranca con valor 50", async ({ page }) => {
    await page.goto("/campaigns");
    const target = page.getByLabel(/objetivo/i);
    await expect(target).toHaveValue("50");
  });

  test("target rechaza valores fuera de min/max via constraint validation", async ({
    page,
  }) => {
    await page.goto("/campaigns");
    const target = page.getByLabel(/objetivo/i);
    // Acceptable: 1 y 500. Vamos a forzar 1000 y verificar que el browser
    // bloquea el submit con `:invalid`.
    await target.fill("1000");
    const valid = await target.evaluate(
      (el: HTMLInputElement) => el.checkValidity(),
    );
    expect(valid).toBe(false);
  });

  // ---------- SSR-dependent (skipped) ----------

  test("tabla del histórico aparece con campañas mockeadas", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021: tabla viene del Server Component");
    await page.goto("/campaigns");
    await expect(page.getByText(/histórico de campañas/i)).toBeVisible();
  });

  test("empty state con cross-links cuando 0 runs", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto("/campaigns");
    await expect(page.getByText(/sin campañas en los últimos 30 días/i)).toBeVisible();
    await expect(page.getByRole("link", { name: "/leads" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Panel" })).toBeVisible();
  });

  test("CampaignProgressCard auto-oculta si no hay activas", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021 + polling requiere mock /campaigns/active");
    await page.goto("/campaigns");
    await expect(page.getByText(/en curso/i)).toHaveCount(0);
  });
});
