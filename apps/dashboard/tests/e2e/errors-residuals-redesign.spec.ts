/**
 * E2E del rediseño /errors + /residual-tasks (bloques 1-4 v0.9.0).
 *
 * Mismo patrón que el resto de specs de rediseño (/leads, /, /campaigns,
 * /projects, /projects/[id]): tests client-side puros ejecutables;
 * tests que verifican contenido del Server Component (KPI values,
 * counts en chips, copy del empty con datos) →
 * `test.skip(SSR_BLOCKED, "WCM-021")`.
 *
 * Ambas páginas son Server Components que fetchan listado + /stats en
 * paralelo, así que la mayoría de cobertura semántica queda pendiente
 * hasta WCM-021 (MSW node).
 */

import { expect, test } from "@playwright/test";

import { installBaseMocks, loginViaCookie } from "./fixtures/api-mocks";

/** Flip a false cuando WCM-021 (MSW node) esté implementado. */
const SSR_BLOCKED = true;

test.describe("/errors — rediseño", () => {
  test.beforeEach(async ({ page }) => {
    await installBaseMocks(page);
    await loginViaCookie(page);
  });

  test("header con título 'Errores recientes' y subtítulo de 7 días", async ({
    page,
  }) => {
    await page.goto("/errors");
    await expect(
      page.getByRole("heading", { name: /errores recientes/i }),
    ).toBeVisible();
    await expect(
      page.getByText(/eventos del sistema en los últimos 7 días/i),
    ).toBeVisible();
  });

  test("KPI strip muestra los 6 stats con sus etiquetas", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto("/errors");
    for (const label of [
      "Total (7d)",
      "Críticos",
      "Errores",
      "Warnings",
      "Componentes",
      "Último crítico",
    ]) {
      await expect(page.getByText(label, { exact: false })).toBeVisible();
    }
  });

  test("header del listado muestra contador de resultados", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021: count viene del Server Component");
    await page.goto("/errors");
    await expect(page.getByText(/\d+\s+resultados?/i)).toBeVisible();
  });

  test("empty 'Sistema estable' con mención de Sentry cuando 0 errores", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto("/errors");
    await expect(page.getByText(/sistema estable/i)).toBeVisible();
    await expect(
      page.getByText(/sin errores registrados en los últimos 7 días/i),
    ).toBeVisible();
    await expect(page.getByText(/sentry/i)).toBeVisible();
  });

  test("filtros chips por severity ocultos si stats.total=0", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021: depende de stats.total");
    await page.goto("/errors");
    // No tiene sentido filtrar 0 cosas — los chips no aparecen.
    const chips = page.getByRole("button", {
      name: /críticos|errores|warnings|info|debug/i,
    });
    await expect(chips).toHaveCount(0);
  });

  test("filtro chip por severity actualiza URL", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021: chips solo aparecen con stats.total>0");
    await page.goto("/errors");
    await page.getByRole("button", { name: /críticos/i }).click();
    await expect(page).toHaveURL(/\?severity=critical/);
  });
});

test.describe("/residual-tasks — rediseño", () => {
  test.beforeEach(async ({ page }) => {
    await installBaseMocks(page);
    await loginViaCookie(page);
  });

  test("header con título 'Tareas residuales' y subtítulo sobre go-live", async ({
    page,
  }) => {
    await page.goto("/residual-tasks");
    await expect(
      page.getByRole("heading", { name: /tareas residuales/i }),
    ).toBeVisible();
    await expect(
      page.getByText(/bloqueantes son las que impiden el go-live/i),
    ).toBeVisible();
  });

  test("KPI strip muestra los 5 stats con sus etiquetas", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto("/residual-tasks");
    for (const label of [
      "Total",
      "Abiertas",
      "Bloqueantes",
      "Proyectos",
      "Tiempo pendiente",
    ]) {
      await expect(page.getByText(label, { exact: true })).toBeVisible();
    }
  });

  test("empty 'Sin tareas residuales' menciona checklist-generator", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto("/residual-tasks");
    await expect(page.getByText(/sin tareas residuales/i)).toBeVisible();
    await expect(page.getByText(/checklist-generator/i)).toBeVisible();
  });

  test("header del listado muestra contador de resultados", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021: count viene del Server Component");
    await page.goto("/residual-tasks");
    await expect(page.getByText(/\d+\s+resultados?/i)).toBeVisible();
  });

  test("filtros chips por status ocultos si stats.total=0", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021: depende de stats.total");
    await page.goto("/residual-tasks");
    const chips = page.getByRole("button", {
      name: /abiertas|en curso|bloqueadas|cerradas|omitidas/i,
    });
    await expect(chips).toHaveCount(0);
  });

  test("filtro chip por status actualiza URL", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021: chips solo aparecen con stats.total>0");
    await page.goto("/residual-tasks");
    await page.getByRole("button", { name: /en curso/i }).click();
    await expect(page).toHaveURL(/\?status=in_progress/);
  });
});
