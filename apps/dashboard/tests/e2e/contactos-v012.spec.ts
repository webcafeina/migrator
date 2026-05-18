/**
 * E2E v0.12.0 — edición de contactos, gestión de leads y plantillas.
 *
 * Spec consolidada (1 fichero) en lugar de 3 separadas — los flujos
 * comparten fixture base y se pueden testear juntos sin overhead.
 * Como siempre: tests client-side puros ejecutables; los que dependen
 * del fetch SSR de datos en Server Components → `test.skip(SSR_BLOCKED,
 * "WCM-021")`.
 */

import { expect, test } from "@playwright/test";

import { installBaseMocks, loginViaCookie } from "./fixtures/api-mocks";

const SSR_BLOCKED = true;

test.describe("v0.12.0 — refactor castellano outreach → contacto", () => {
  test.beforeEach(async ({ page }) => {
    await installBaseMocks(page);
    await loginViaCookie(page);
  });

  test("ficha del lead usa 'Componer contacto →' (no 'outreach')", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021: depende del SSR fetch del lead");
    await page.goto("/leads?selected=1");
    await expect(
      page.getByRole("button", { name: /componer contacto/i }),
    ).toBeVisible();
    // Guardia: NO debe quedar texto antiguo "Componer outreach".
    await expect(
      page.getByRole("button", { name: /componer outreach/i }),
    ).toHaveCount(0);
  });

  test("sección de la ficha se titula 'Contacto comercial'", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto("/leads?selected=1");
    await expect(
      page.getByRole("heading", { name: /^contacto comercial$/i }),
    ).toBeVisible();
  });
});

test.describe("v0.12.0 — gestión de leads (descartar + borrar)", () => {
  test.beforeEach(async ({ page }) => {
    await installBaseMocks(page);
    await loginViaCookie(page);
  });

  test("botón 'Borrar definitivo' abre dialog con typing-to-confirm", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021: depende de LeadActions con lead cargado");
    await page.goto("/leads?selected=1");
    await page.getByRole("button", { name: /borrar definitivo/i }).click();
    await expect(
      page.getByRole("dialog", { name: /borrar lead permanentemente/i }),
    ).toBeVisible();
    // Botón rojo deshabilitado hasta tipear el nombre exacto.
    const danger = page.getByRole("button", {
      name: /borrar permanentemente/i,
    });
    await expect(danger).toBeDisabled();
  });

  test("dialog cierra con Escape", async ({ page }) => {
    test.skip(SSR_BLOCKED, "WCM-021");
    await page.goto("/leads?selected=1");
    await page.getByRole("button", { name: /borrar definitivo/i }).click();
    await page.keyboard.press("Escape");
    await expect(
      page.getByRole("dialog", { name: /borrar lead permanentemente/i }),
    ).toHaveCount(0);
  });
});

test.describe("v0.12.0 — pantalla CRUD plantillas", () => {
  test.beforeEach(async ({ page }) => {
    await installBaseMocks(page);
    await loginViaCookie(page);
  });

  test("/settings/templates muestra header castellano y back link", async ({
    page,
  }) => {
    await page.goto("/settings/templates");
    await expect(
      page.getByRole("heading", { name: /plantillas de contacto/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: /volver a ajustes/i }),
    ).toHaveAttribute("href", "/settings");
  });

  test("microcopy explica que sequences ya generadas NO se ven afectadas", async ({
    page,
  }) => {
    await page.goto("/settings/templates");
    await expect(
      page.getByText(/sequences ya generadas no se ven afectadas/i),
    ).toBeVisible();
  });

  test("microcopy de RBAC visible: 'solo administradores'", async ({
    page,
  }) => {
    await page.goto("/settings/templates");
    await expect(
      page.getByText(/solo administradores/i),
    ).toBeVisible();
  });
});

test.describe("v0.12.0 — firma read-only en /settings", () => {
  test.beforeEach(async ({ page }) => {
    await installBaseMocks(page);
    await loginViaCookie(page);
  });

  test("card 'Firma legal aplicada al contacto' visible", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021: depende del SSR fetch /system/firma");
    await page.goto("/settings");
    await expect(
      page.getByText(/firma legal aplicada al contacto/i),
    ).toBeVisible();
  });

  test("card 'Plantillas de contacto' enlaza a /settings/templates", async ({
    page,
  }) => {
    test.skip(SSR_BLOCKED, "WCM-021: depende del SSR fetch de la página");
    await page.goto("/settings");
    const link = page.getByRole("link", {
      name: /gestionar plantillas jinja2/i,
    });
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute("href", "/settings/templates");
  });
});
