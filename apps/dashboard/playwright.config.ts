import { defineConfig, devices } from "@playwright/test";

// E2E del dashboard. Estrategia:
// - Playwright arranca `next dev -p 3100` durante los tests (puerto raro
//   para no chocar con el dev server humano).
// - Todas las llamadas a `/api/*` se interceptan con `page.route()` en
//   cada test, devolviendo fixtures controladas. No tocamos red real.
// - Tests headless en CI; modo `--ui` en local con `pnpm e2e:ui`.
//
// Visual regression con `expect(page).toHaveScreenshot()`. Baselines
// versionadas en `tests/e2e/__screenshots__/`.

const PORT = 3100;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false, // dashboard interno, no necesita paralelismo
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    locale: "es-ES",
    timezoneId: "Europe/Madrid",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    // Invocamos `next` directamente (no `pnpm dev`) porque el script
    // dev del package.json tiene `-p 3000` hardcoded, y `pnpm dev -- -p 3100`
    // se expande a `next dev -p 3000 -- -p 3100` que Next interpreta
    // como project dir y rompe en CI.
    command: `pnpm exec next dev -p ${PORT}`,
    url: `http://127.0.0.1:${PORT}/login`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    stdout: "pipe",
    stderr: "pipe",
    env: {
      // El dashboard solo necesita estas dos para arrancar dev mode.
      // La API real no se contacta — todas las requests se interceptan.
      NEXT_PUBLIC_API_URL: `http://127.0.0.1:${PORT}/api`,
      NODE_ENV: "development",
    },
  },
});
