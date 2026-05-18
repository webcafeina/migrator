/**
 * E2E del rediseño v0.11.0 — alta manual de leads en /leads/new.
 *
 * Mismo patrón que las otras specs de rediseño:
 * - Tests client-side puros ejecutables (header castellano, tabs,
 *   guardia "no menciona Fase X", botón outline en /leads).
 * - Tests que dependen del Server fetch de suggestions →
 *   `test.skip(SSR_BLOCKED, "WCM-021")`.
 */

import { expect, test } from "@playwright/test";

import { installBaseMocks, loginViaCookie } from "./fixtures/api-mocks";

/** Flip a false cuando WCM-021 (MSW node) esté implementado. */
const SSR_BLOCKED = true;

test.describe("/leads — entrada al alta manual", () => {
  test.beforeEach(async ({ page }) => {
    await installBaseMocks(page);
    await loginViaCookie(page);
  });

  test("botón '+ Nuevo lead' visible en cabecera y enlaza a /leads/new", async ({
    page,
  }) => {
    await page.goto("/leads");
    const link = page.getByRole("link", { name: /\+ nuevo lead/i });
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute("href", "/leads/new");
  });
});

test.describe("/leads/new — rediseño v0.11.0", () => {
  test.beforeEach(async ({ page }) => {
    await installBaseMocks(page);
    await loginViaCookie(page);
  });

  test("header con título 'Nuevo lead' y microcopy explicativa", async ({
    page,
  }) => {
    await page.goto("/leads/new");
    await expect(
      page.getByRole("heading", { name: /^nuevo lead$/i }),
    ).toBeVisible();
    await expect(
      page.getByText(/sin lanzar una campaña.*fingerprint.*enrich/i),
    ).toBeVisible();
  });

  test("2 tabs ARIA: 'Una URL' y 'Pegar lote'", async ({ page }) => {
    await page.goto("/leads/new");
    await expect(page.getByRole("tab", { name: /una url/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /pegar lote/i })).toBeVisible();
  });

  test("click 'Pegar lote' muestra textarea con preview live", async ({
    page,
  }) => {
    await page.goto("/leads/new");
    await page.getByRole("tab", { name: /pegar lote/i }).click();
    const textarea = page.getByLabel(/urls.*1 por l[ií]nea/i);
    await expect(textarea).toBeVisible();
    await textarea.fill("https://a.com\n# ignorado\nhttps://b.com");
    await expect(page.getByText(/2 URLs válidas/i)).toBeVisible();
  });

  test("microcopy legal menciona art. 6.1.f + payload.source", async ({
    page,
  }) => {
    await page.goto("/leads/new");
    await expect(page.getByText(/art\.\s*6\.1\.f/i)).toBeVisible();
    await expect(page.getByText(/manual_single/i)).toBeVisible();
    await expect(page.getByText(/manual_bulk/i)).toBeVisible();
  });

  test("breadcrumb '← Volver a la lista' enlaza a /leads", async ({ page }) => {
    await page.goto("/leads/new");
    const back = page.getByRole("link", { name: /volver a la lista/i });
    await expect(back).toBeVisible();
    await expect(back).toHaveAttribute("href", "/leads");
  });

  test("submit single 201 → toast verde + redirige a /leads?selected=N", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021: depende del SSR fetch de suggestions");
    await page.goto("/leads/new");
    await page.getByLabel(/^url/i).fill("https://nuevo.com");
    await page.getByRole("button", { name: /crear lead/i }).click();
    await expect(page).toHaveURL(/\/leads\?selected=\d+/);
  });

  test("submit single 409 → toast.error + botón 'Abrir lead existente'", async ({
    page,
  }) => {
    // Override: 409 con existing_lead_id
    await page.route(/\/api\/v1\/leads$/, (route) => {
      if (route.request().method() === "POST") {
        return route.fulfill({
          status: 409,
          contentType: "application/json",
          body: JSON.stringify({
            error: {
              code: "conflict",
              message: "Lead con esa URL ya existe",
              details: { existing_lead_id: 7 },
            },
          }),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "[]",
      });
    });
    await page.goto("/leads/new");
    await page.getByLabel(/^url/i).fill("https://duplicada.com");
    await page.getByRole("button", { name: /crear lead/i }).click();
    const existingLink = page.getByRole("link", {
      name: /abrir lead existente/i,
    });
    await expect(existingLink).toBeVisible();
    await expect(existingLink).toHaveAttribute("href", "/leads?selected=7");
  });
});
