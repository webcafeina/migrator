/**
 * E2E del rediseño /projects/[id] + sub-páginas (bloques 1-4).
 *
 * Mismo patrón que las specs anteriores (/leads, /, /campaigns,
 * /projects): tests client-side puros ejecutables; tests que verifican
 * contenido del Server Component (header, fases, tabs con badges,
 * status pills) → `test.skip(SSR_BLOCKED, "WCM-021")`.
 *
 * El detalle requiere ID válido + fetch del Server Component (project +
 * summary + phases/residuals). Como la mayoría depende de SSR data,
 * casi toda la cobertura aquí queda skipped hasta WCM-021.
 */

import { expect, test } from "@playwright/test";

import { installBaseMocks, loginViaCookie } from "./fixtures/api-mocks";

/** Flip a false cuando WCM-021 (MSW node) esté implementado. */
const SSR_BLOCKED = true;

const PROJECT_ID = 1;

test.describe("/projects/[id] — overview", () => {
  test.beforeEach(async ({ page }) => {
    await installBaseMocks(page);
    await loginViaCookie(page);
  });

  test("404 cuando el proyecto no existe", async ({ page }) => {
    test.skip(
      SSR_BLOCKED,
      "WCM-021: el fetch del Server Component a /projects/{id} no se intercepta con page.route()",
    );
    await page.route(`**/api/v1/projects/99999`, (route) =>
      route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({
          error: { code: "not_found", message: "Project 99999 no encontrado" },
        }),
      }),
    );
    const resp = await page.goto("/projects/99999");
    expect(resp?.status()).toBe(404);
  });

  test("breadcrumb '← Proyectos' enlaza al listado", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021: requiere fetch del proyecto");
    await page.goto(`/projects/${PROJECT_ID}`);
    const back = page.getByRole("link", { name: /proyectos/i });
    await expect(back).toBeVisible();
    await expect(back).toHaveAttribute("href", "/projects");
  });

  test("3 tabs visibles con el Overview activo", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto(`/projects/${PROJECT_ID}`);
    await expect(page.getByText("Overview")).toBeVisible();
    await expect(page.getByText("Checklist")).toBeVisible();
    await expect(page.getByText("Visual diff")).toBeVisible();
    await expect(page.getByText("Overview").locator("..")).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  test("PhaseProgressBar muestra N/M de fases completadas", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto(`/projects/${PROJECT_ID}`);
    // Forma N/M (5/15, 0/15, etc.)
    await expect(page.getByText(/\d+\/\d+/)).toBeVisible();
  });

  test("Timeline lista las fases con icono por status", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto(`/projects/${PROJECT_ID}`);
    // Al menos status pills castellanas presentes
    const pills = page.getByText(/en curso|ok|pendiente|fallo|omitida/i);
    expect(await pills.count()).toBeGreaterThan(0);
  });

  test("ConfigPanel muestra builder/destino/multilang", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto(`/projects/${PROJECT_ID}`);
    await expect(page.getByText(/destino/i)).toBeVisible();
    await expect(page.getByText(/builder/i)).toBeVisible();
    await expect(page.getByText(/multilang/i)).toBeVisible();
  });

  test("empty timeline cuando 0 fases sugiere 'Pulsa Start'", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto(`/projects/${PROJECT_ID}`);
    await expect(
      page.getByText(/pipeline sin arrancar todavía/i),
    ).toBeVisible();
  });
});

test.describe("/projects/[id]/checklist", () => {
  test.beforeEach(async ({ page }) => {
    await installBaseMocks(page);
    await loginViaCookie(page);
  });

  test("Tab Checklist activo en pathname /checklist", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto(`/projects/${PROJECT_ID}/checklist`);
    await expect(page.getByText("Checklist").locator("..")).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  test("Header del listado muestra abiertas/cerradas/total", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto(`/projects/${PROJECT_ID}/checklist`);
    await expect(
      page.getByText(/\d+\s+abiertas\s+·\s+\d+\s+cerradas\s+·\s+\d+\s+total/i),
    ).toBeVisible();
  });

  test("Empty state explica al operador qué genera las tareas", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto(`/projects/${PROJECT_ID}/checklist`);
    await expect(
      page.getByText(/checklist-generator/i),
    ).toBeVisible();
  });

  test("Categoría 'Bloqueantes para go-live' visible con orden canónico", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto(`/projects/${PROJECT_ID}/checklist`);
    // El header de categoría aparece en uppercase
    await expect(
      page.getByText(/bloqueantes para go-live/i),
    ).toBeVisible();
  });
});

test.describe("/projects/[id]/diff", () => {
  test.beforeEach(async ({ page }) => {
    await installBaseMocks(page);
    await loginViaCookie(page);
  });

  test("Tab Visual diff activo en pathname /diff", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto(`/projects/${PROJECT_ID}/diff`);
    await expect(
      page.getByText("Visual diff").locator(".."),
    ).toHaveAttribute("aria-current", "page");
  });

  test("Placeholder honesto menciona packages/visual-diff", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto(`/projects/${PROJECT_ID}/diff`);
    await expect(
      page.getByText(/packages\/visual-diff/i),
    ).toBeVisible();
  });

  test("NO menciona la mentira obsoleta 'Fase 10'", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto(`/projects/${PROJECT_ID}/diff`);
    // El placeholder anterior decía "se implementa en Fase 10" (falso
    // desde hace meses). Si vuelve a colarse, este test falla.
    await expect(page.getByText(/se implementa en fase 10/i)).toHaveCount(0);
  });
});
