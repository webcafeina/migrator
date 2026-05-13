import { test, expect } from "@playwright/test";
import { installBaseMocks, loginViaCookie } from "./fixtures/api-mocks";

// Visual regression: captura las páginas clave y compara contra
// baselines en `__screenshots__/`. Para regenerar tras un cambio
// intencionado: `pnpm e2e -- --update-snapshots`.
//
// En CI, los snapshots ARM (Apple Silicon) vs x64 (GitHub runners)
// difieren mínimamente; toleramos un 1% de pixel diff.

test.describe("Visual regression", () => {
  test.beforeEach(async ({ page }) => {
    await installBaseMocks(page);
    await loginViaCookie(page);
  });

  test("dashboard overview", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveScreenshot("overview.png", {
      maxDiffPixelRatio: 0.01,
      fullPage: true,
    });
  });

  test("leads list", async ({ page }) => {
    await page.goto("/leads");
    // Esperar a que renderice todo
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveScreenshot("leads.png", {
      maxDiffPixelRatio: 0.01,
      fullPage: true,
    });
  });
});
