import { test, expect } from "@playwright/test";
import { installBaseMocks } from "./fixtures/api-mocks";

test.describe("Login", () => {
  test("muestra el formulario y permite iniciar sesión", async ({ page }) => {
    await installBaseMocks(page);

    await page.goto("/login");
    await expect(page.getByText("WEBCAFEÍNA MIGRATOR")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Iniciar sesión" })).toBeVisible();

    await page.getByLabel(/email/i).fill("ops@webcafeina.com");
    await page.getByLabel(/password|contraseña/i).fill("hunter2");
    await page.getByRole("button", { name: /entrar|iniciar/i }).click();

    // Tras el login, el middleware redirige a "/" (overview)
    await expect(page).toHaveURL(/\/$/);
  });

  test("error de credenciales muestra toast", async ({ page }) => {
    await page.route("**/api/v1/auth/login", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({
          error: { code: "unauthorized", message: "Credenciales inválidas" },
        }),
      }),
    );

    await page.goto("/login");
    await page.getByLabel(/email/i).fill("ops@webcafeina.com");
    await page.getByLabel(/password|contraseña/i).fill("wrong");
    await page.getByRole("button", { name: /entrar|iniciar/i }).click();

    // Toast aparece con el mensaje del backend
    await expect(page.getByText(/credenciales/i)).toBeVisible({ timeout: 5_000 });
  });
});
