/**
 * E2E del rediseño master-detail de /leads (bloques 1-4).
 *
 * Estado actual:
 * - Tests puramente client-side (keyboard shortcuts, URL transitions
 *   sin depender del contenido fetchado) → ejecutables y pasan.
 * - Tests que verifican el contenido renderizado por el Server
 *   Component (lista, detalle, banner, stats topbar) → marcados con
 *   `test.skip(SSR_BLOCKED)` porque `page.route()` no intercepta el
 *   fetch del lado Node — ver WCM-021. Pasarán automáticamente cuando
 *   se introduzca MSW node como interceptor (opción A de WCM-021).
 *
 * Mientras tanto: los tests skip documentan el comportamiento esperado
 * y sirven como contrato cuando se implemente la solución definitiva.
 */

/** Toggle único — flip a `false` cuando MSW interceptación esté lista. */
const SSR_BLOCKED = true;

import { expect, test } from "@playwright/test";

import {
  FIXTURE_LEADS,
  installBaseMocks,
  loginViaCookie,
} from "./fixtures/api-mocks";

test.describe("/leads — rediseño master-detail", () => {
  test.beforeEach(async ({ page }) => {
    await installBaseMocks(page);
    await loginViaCookie(page);
  });

  test("topbar muestra los stats agregados", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021: Server Components no interceptados por page.route()");
    await page.goto("/leads");

    // Stats compuestos: "2 leads · 2 sin contactar · ..."
    // Comprobamos los números pivote sin atarnos a separadores.
    await expect(page.getByText(/\b2\b\s*leads/)).toBeVisible();
    await expect(page.getByText(/sin contactar/i)).toBeVisible();
    await expect(page.getByText(/score medio/i)).toBeVisible();
    await expect(page.getByText(/builders/i)).toBeVisible();
  });

  test("lista renderiza items con nombre comercial y score", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto("/leads");
    await expect(page.getByText("Bar Pepe")).toBeVisible();
    await expect(page.getByText("Hostel Papy")).toBeVisible();

    // Los scores aparecen en la lista (mockeados a 75 y 35).
    const ol = page.locator('ol[aria-label="Lista de leads"]');
    await expect(ol.getByText("75")).toBeVisible();
    await expect(ol.getByText("35")).toBeVisible();
  });

  test("empty state visible cuando no hay lead seleccionado", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto("/leads");
    await expect(page.getByText(/sin selección/i)).toBeVisible();
    await expect(
      page.getByText(/Selecciona un lead de la lista/i),
    ).toBeVisible();
  });

  test("click en item actualiza ?selected y muestra el detalle", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto("/leads");

    // Click en Bar Pepe (primer item por score)
    await page
      .locator('ol[aria-label="Lista de leads"] [role="button"]')
      .first()
      .click();

    // URL refleja la selección.
    await expect(page).toHaveURL(/\?selected=1$/);

    // El detalle aparece a la derecha con el nombre del lead.
    const detail = page.getByLabel("Detalle del lead seleccionado");
    await expect(detail).toBeVisible();
    await expect(detail.getByRole("heading", { name: "Bar Pepe" })).toBeVisible();

    // El score panel muestra la cifra grande.
    await expect(detail.getByText("75", { exact: true })).toBeVisible();
  });

  test("acceder con ?selected= en URL pre-selecciona el lead", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto(`/leads?selected=${FIXTURE_LEADS[1]!.id}`);
    const detail = page.getByLabel("Detalle del lead seleccionado");
    await expect(detail.getByRole("heading", { name: "Hostel Papy" })).toBeVisible();
  });

  test("acciones primarias visibles en el detalle", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto("/leads?selected=1");
    const detail = page.getByLabel("Detalle del lead seleccionado");

    await expect(
      detail.getByRole("button", { name: /componer outreach/i }),
    ).toBeVisible();
    await expect(
      detail.getByRole("button", { name: /convertir a proyecto/i }),
    ).toBeVisible();
    await expect(
      detail.getByRole("button", { name: /re-fingerprint/i }),
    ).toBeVisible();
    await expect(
      detail.getByRole("button", { name: /opt-out/i }),
    ).toBeVisible();
  });

  test("componer outreach: muestra mensaje de éxito tras click", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    // Mock específico del endpoint de compose
    await page.route(
      "**/api/v1/leads/1/outreach/compose",
      (route) =>
        route.fulfill({
          status: 202,
          contentType: "application/json",
          body: JSON.stringify({ task_id: "task-abc", status: "queued" }),
        }),
    );

    await page.goto("/leads?selected=1");
    const composeBtn = page.getByRole("button", { name: /componer outreach/i });
    await composeBtn.click();

    // Mensaje "✓ Borrador encolado" aparece junto a los botones.
    await expect(page.getByText(/borrador encolado/i)).toBeVisible({
      timeout: 3000,
    });
  });

  test("componer outreach disabled si el lead no tiene emails", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    // Hostel Papy (id 2) no tiene emails en la fixture.
    await page.goto("/leads?selected=2");
    const composeBtn = page.getByRole("button", { name: /componer outreach/i });
    await expect(composeBtn).toBeDisabled();
    await expect(composeBtn).toHaveAttribute(
      "title",
      /sin emails.*enrich/i,
    );
  });

  test("convertir a proyecto + opt-out están disabled con tooltip explicativo", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto("/leads?selected=1");
    const convert = page.getByRole("button", { name: /convertir a proyecto/i });
    const optOut = page.getByRole("button", { name: /opt-out/i });
    await expect(convert).toBeDisabled();
    await expect(optOut).toBeDisabled();
    await expect(convert).toHaveAttribute("title", /implementación/i);
    await expect(optOut).toHaveAttribute("title", /pendiente/i);
  });

  test("Escape limpia la selección", async ({ page }) => {
    await page.goto("/leads?selected=1");
    await expect(page).toHaveURL(/selected=1/);
    // El listener vive en `document`. Aseguramos foco en body para que
    // el keydown llegue (algunos navegadores headless sin foco previo
    // no propagan teclas globales).
    await page.locator("body").click({ position: { x: 5, y: 5 } });
    await page.keyboard.press("Escape");
    await expect(page).not.toHaveURL(/selected=/);
  });

  test("ArrowDown selecciona el siguiente lead", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021: requiere lista cargada para resolver vecindad");
    await page.goto("/leads?selected=1");
    await page.keyboard.press("ArrowDown");
    await expect(page).toHaveURL(/selected=2/);
  });

  test("Enter abre el lead en full-page", async ({ page }) => {
    // El endpoint /leads/{id} es SSR — el navigation puede fallar si el
    // page del detalle hace su propio fetch. Mockeamos la respuesta GET.
    await page.route("**/api/v1/leads/1", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(FIXTURE_LEADS[0]),
      }),
    );
    await page.goto("/leads?selected=1");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/leads\/1$/);
  });
});

test.describe("/leads — banner borrador outreach", () => {
  test("aparece cuando lead.status === 'outreach_prepared'", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await loginViaCookie(page);

    // Override leads list para incluir uno con status outreach_prepared.
    const preparedLead = {
      ...FIXTURE_LEADS[0]!,
      id: 99,
      business_name: "Lead Preparado",
      status: "outreach_prepared",
    };
    await page.route(/\/api\/v1\/leads(\?.*)?$/, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([preparedLead]),
      }),
    );
    await page.route(/\/api\/v1\/leads\/stats/, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          total: 1,
          uncontacted: 0,
          avg_score: preparedLead.score,
          distinct_builders: 1,
          distinct_sectors: 1,
          distinct_regions: 1,
        }),
      }),
    );
    await page.route("**/api/v1/auth/me", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "u",
          email: "ops@webcafeina.com",
          role: "operator",
          name: "Operadora",
        }),
      }),
    );

    await page.goto("/leads?selected=99");
    await expect(page.getByText(/borrador outreach preparado/i)).toBeVisible();
    await expect(
      page.getByRole("link", { name: /revisar/i }),
    ).toBeVisible();
  });
});
