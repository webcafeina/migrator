/**
 * E2E del rediseño Panel/Overview (bloques 1-4).
 *
 * Mismo patrón que `/leads`: tests puramente client-side ejecutables;
 * tests que verifican contenido del Server Component → marcados con
 * `test.skip(SSR_BLOCKED, "WCM-021")`. Pasarán automáticamente cuando
 * MSW node esté enchufado.
 */

import { expect, test } from "@playwright/test";

import { installBaseMocks, loginViaCookie } from "./fixtures/api-mocks";

/** Flip a `false` cuando WCM-021 (MSW node) esté implementado. */
const SSR_BLOCKED = true;

test.describe("/ — Panel rediseñado", () => {
  test.beforeEach(async ({ page }) => {
    await installBaseMocks(page);
    await loginViaCookie(page);
  });

  test("header global muestra badge de entorno con dot de color", async ({
    page,
  }) => {
    await page.goto("/");
    // El badge "entorno · dev" lo renderiza el Header global desde
    // process.env.NODE_ENV. En el webServer de Playwright NODE_ENV=development
    // (configurado en playwright.config.ts).
    await expect(page.getByText(/entorno\s*·\s*dev/i)).toBeVisible();
  });

  test("KPI strip muestra 5 stats con label y valor", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto("/");
    for (const label of [
      "Leads totales",
      "Sin contactar",
      "Proyectos activos",
      "Tareas pendientes",
      "Errores (24h)",
    ]) {
      await expect(page.getByText(label)).toBeVisible();
    }
  });

  test("KPIs son links a las páginas correspondientes", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto("/");
    await expect(
      page.getByRole("link", { name: /leads totales/i }),
    ).toHaveAttribute("href", "/leads");
    await expect(
      page.getByRole("link", { name: /proyectos activos/i }),
    ).toHaveAttribute("href", "/projects");
    await expect(
      page.getByRole("link", { name: /errores/i }),
    ).toHaveAttribute("href", "/errors");
  });

  test("acción primaria '+ Lanzar campaña' enlaza a /campaigns", async ({
    page,
  }) => {
    await page.goto("/");
    const cta = page.getByRole("link", { name: /lanzar campaña/i });
    await expect(cta).toBeVisible();
    await expect(cta).toHaveAttribute("href", "/campaigns");
  });

  test("feed agrupa eventos por día con encabezado", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto("/");
    // Con fixtures vacías el feed muestra empty state; con datos reales
    // mostraría encabezados "Hoy", "Ayer", etc. Verificamos el header
    // de sección.
    await expect(page.getByText("Actividad reciente")).toBeVisible();
  });

  test("filtro chip por action actualiza URL", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto("/");
    await page.getByRole("button", { name: /enriquecer/i }).click();
    await expect(page).toHaveURL(/\?action=enrich/);
  });

  test("filtro activo se refleja con aria-pressed", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto("/?action=enrich");
    const chip = page.getByRole("button", { name: /enriquecer/i });
    await expect(chip).toHaveAttribute("aria-pressed", "true");
  });
});

test.describe("/ — onboarding cuando sistema vacío", () => {
  test("muestra card de bienvenida si 0 leads + 0 proyectos + 0 eventos", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await loginViaCookie(page);

    // Override mocks para sistema completamente vacío.
    await page.route(/\/api\/v1\/leads(\?.*)?$/, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "[]",
      }),
    );
    await page.route(/\/api\/v1\/leads\/stats/, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          total: 0,
          uncontacted: 0,
          avg_score: null,
          distinct_builders: 0,
          distinct_sectors: 0,
          distinct_regions: 0,
        }),
      }),
    );
    await page.route(/\/api\/v1\/projects(\?.*)?$/, (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
    );
    await page.route(/\/api\/v1\/audit-log/, (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
    );

    await page.goto("/");
    await expect(page.getByText(/sistema recién provisionado/i)).toBeVisible();
    await expect(
      page.getByRole("link", { name: /lanzar primera campaña/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: /configuración del entorno/i }),
    ).toBeVisible();
  });
});
