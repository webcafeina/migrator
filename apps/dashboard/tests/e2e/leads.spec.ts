import { test, expect } from "@playwright/test";
import { installBaseMocks, loginViaCookie, FIXTURE_LEADS } from "./fixtures/api-mocks";

// /leads y /leads/[id] son Server Components: hacen el fetch en Node antes
// de mandar HTML al browser. page.route() intercepta requests del browser
// y por tanto NO mockea esos fetch — el server intenta llegar al API real
// (http://localhost:8000) y falla con ECONNREFUSED en CI.
// Para testear esto correctamente necesitamos un mock server HTTP real
// (MSW node, http-server, etc.) corriendo en paralelo al webServer Next.
// Tracking: WCM-021.
test.describe.skip("Leads (skip — requiere mock server real para Server Components, WCM-021)", () => {
  test.beforeEach(async ({ page }) => {
    await installBaseMocks(page);
    await loginViaCookie(page);
  });

  test("lista los leads con badges y filtros", async ({ page }) => {
    await page.goto("/leads");

    for (const lead of FIXTURE_LEADS) {
      await expect(page.getByText(lead.business_name)).toBeVisible();
    }

    // Filtro por sector (por ejemplo)
    await expect(page.getByText("restauración")).toBeVisible();
    await expect(page.getByText("Bar Pepe")).toBeVisible();
  });

  test("acceso a detalle del lead", async ({ page }) => {
    const lead = FIXTURE_LEADS[0]!;
    await page.route(/\/api\/v1\/leads\/1$/, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(lead),
      }),
    );

    await page.goto("/leads");
    await page.getByRole("link", { name: lead.business_name }).click();
    await expect(page).toHaveURL(/\/leads\/1/);
    await expect(page.getByText(lead.url)).toBeVisible();
  });
});
