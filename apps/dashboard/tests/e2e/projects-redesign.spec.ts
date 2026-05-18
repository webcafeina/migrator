/**
 * E2E del rediseño /projects (bloques 1-4).
 *
 * Mismo patrón que /leads, /, /campaigns: tests client-side puros
 * ejecutables; tests que verifican contenido del Server Component
 * (KPI values, tabla, chips counts, empty state copy) →
 * `test.skip(SSR_BLOCKED, "WCM-021")`.
 */

import { expect, test } from "@playwright/test";

import { installBaseMocks, loginViaCookie } from "./fixtures/api-mocks";

/** Flip a false cuando WCM-021 (MSW node) esté implementado. */
const SSR_BLOCKED = true;

test.describe("/projects — rediseño", () => {
  test.beforeEach(async ({ page }) => {
    await installBaseMocks(page);
    await loginViaCookie(page);
  });

  test("header con título 'Proyectos' y subtítulo descriptivo", async ({
    page,
  }) => {
    await page.goto("/projects");
    await expect(
      page.getByRole("heading", { name: /^proyectos$/i }),
    ).toBeVisible();
    await expect(
      page.getByText(/migraciones de web origen.*wordpress.*bricks/i),
    ).toBeVisible();
  });

  test("acción primaria '+ Nuevo proyecto' enlaza a /leads", async ({
    page,
  }) => {
    await page.goto("/projects");
    const cta = page.getByRole("link", { name: /\+ nuevo proyecto/i });
    await expect(cta).toBeVisible();
    await expect(cta).toHaveAttribute("href", "/leads");
    // El tooltip explica el modelo mental (proyecto = lead convertido).
    await expect(cta).toHaveAttribute(
      "title",
      /proyectos nacen de un lead cualificado/i,
    );
  });

  test("header del listado muestra contador de resultados", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021: count viene del Server Component");
    await page.goto("/projects");
    await expect(page.getByText(/\d+\s+resultados?/i)).toBeVisible();
  });

  test("KPI strip muestra los 5 stats con sus etiquetas", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto("/projects");
    for (const label of [
      "Proyectos",
      "En curso",
      "Bloqueados",
      "Completados",
      "Diff medio",
    ]) {
      await expect(page.getByText(label, { exact: true })).toBeVisible();
    }
  });

  test("empty state con CTAs aparece cuando no hay proyectos", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto("/projects");
    await expect(page.getByText(/sin proyectos todavía/i)).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /convierte un lead cualificado/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: /ir a leads/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: /ver actividad del panel/i }),
    ).toBeVisible();
  });

  test("filtros chips por status ocultos si total=0", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021: depende de stats.total");
    await page.goto("/projects");
    // Cuando no hay proyectos, no debe haber chips (no tiene sentido
    // filtrar 0 cosas). Los chips usan rol "button" + aria-pressed.
    const chips = page.getByRole("button", { name: /encolados|en curso|bloqueados/i });
    await expect(chips).toHaveCount(0);
  });

  test("filtro chip por status actualiza URL", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021: chips solo aparecen con stats.total>0");
    // Para activar este test (cuando MSW): mock /projects/stats con
    // total > 0 y verificar que clic en chip "en curso" mete
    // ?status=running en la URL.
    await page.goto("/projects");
    await page.getByRole("button", { name: /en curso/i }).click();
    await expect(page).toHaveURL(/\?status=running/);
  });
});
