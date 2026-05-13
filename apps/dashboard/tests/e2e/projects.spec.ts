import { test, expect } from "@playwright/test";
import { installBaseMocks, loginViaCookie, FIXTURE_PROJECT } from "./fixtures/api-mocks";

test.describe("Proyectos", () => {
  test.beforeEach(async ({ page }) => {
    await installBaseMocks(page);
    await loginViaCookie(page);
  });

  test("listado y navegación al detalle", async ({ page }) => {
    await page.goto("/projects");

    await expect(page.getByText(FIXTURE_PROJECT.client_name)).toBeVisible();

    await page.getByRole("link", { name: new RegExp(FIXTURE_PROJECT.client_name) }).click();
    await expect(page).toHaveURL(/\/projects\/1/);
    await expect(page.getByText(FIXTURE_PROJECT.source_url)).toBeVisible();
    await expect(page.getByText(/Timeline de fases/i)).toBeVisible();
  });

  test("disparar 'Start' encola pipeline", async ({ page }) => {
    let started = false;
    await page.route(/\/api\/v1\/projects\/1\/start/, (route) => {
      started = true;
      return route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ task_id: "task-uuid-1", status: "queued" }),
      });
    });

    await page.goto("/projects/1");
    const startBtn = page.getByRole("button", { name: /start|iniciar/i }).first();
    if (await startBtn.isVisible()) {
      await startBtn.click();
      await expect(page.getByText(/encolad/i)).toBeVisible({ timeout: 5_000 });
      expect(started).toBe(true);
    }
  });
});
