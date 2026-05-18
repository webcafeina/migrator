// Mocks de la API para los e2e. Cada test importa lo que necesite e
// instala los handlers con `page.route()`.
//
// Convención: los handlers devuelven JSON listo para servir. Las URLs
// usan path absoluto (sin host) para que coincidan con el rewrite del
// next.config.mjs.

import type { Page, Route } from "@playwright/test";

export const FIXTURE_USER = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "ops@webcafeina.com",
  role: "operator",
  name: "Operadora",
};

export const FIXTURE_LEADS = [
  {
    id: 1,
    url: "https://barpepe.es",
    business_name: "Bar Pepe",
    sector: "restauración",
    region: "Cáceres",
    country: "ES",
    builder_detected: "wix",
    builder_confidence: 0.92,
    builder_evidence: [],
    emails: ["hola@barpepe.es"],
    phones: ["+34666111222"],
    social_links: {},
    status: "enriched",
    score: 75,
    last_crawl_at: null,
    embedding_model: null,
    embedding_at: null,
    created_at: "2026-05-12T10:00:00Z",
    updated_at: "2026-05-12T10:00:00Z",
  },
  {
    id: 2,
    url: "https://hostelpapy.com",
    business_name: "Hostel Papy",
    sector: "alojamiento",
    region: "Madrid",
    country: "ES",
    builder_detected: "hostinger_ai",
    builder_confidence: 0.81,
    builder_evidence: [],
    emails: [],
    phones: [],
    social_links: {},
    status: "fingerprinted",
    score: 35,
    last_crawl_at: null,
    embedding_model: null,
    embedding_at: null,
    created_at: "2026-05-11T10:00:00Z",
    updated_at: "2026-05-11T10:00:00Z",
  },
];

export const FIXTURE_PROJECT = {
  id: 1,
  client_name: "Bar Pepe",
  source_url: "https://barpepe.es",
  target_domain: "barpepe.com",
  builder_source: "wix",
  has_ecommerce: false,
  is_multilang: false,
  langs: [],
  asset_storage: "wp_local",
  preserve_paths: true,
  status: "queued",
  started_at: null,
  completed_at: null,
  estimated_go_live_at: null,
  visual_diff_avg_score: null,
  created_at: "2026-05-13T09:00:00Z",
  updated_at: "2026-05-13T09:00:00Z",
};

/**
 * Mock genérico: intercepta auth/me, leads list y project detail.
 * Cada test extiende esto con sus mocks específicos.
 */
export async function installBaseMocks(page: Page): Promise<void> {
  await page.route("**/api/v1/auth/me", (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(FIXTURE_USER) }),
  );
  await page.route("**/api/v1/auth/login", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: {
        // El dashboard solo comprueba la cookie `wcm_session` para saber
        // si está logueado. Set-Cookie funciona en route.fulfill.
        "Set-Cookie": "wcm_session=fake-jwt; Path=/; HttpOnly",
      },
      body: JSON.stringify({ token: "fake-jwt", user: FIXTURE_USER }),
    }),
  );
  await page.route("**/api/v1/auth/logout", (route: Route) =>
    route.fulfill({
      status: 204,
      headers: { "Set-Cookie": "wcm_session=; Path=/; Max-Age=0" },
    }),
  );
  await page.route(/\/api\/v1\/leads(\?.*)?$/, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(FIXTURE_LEADS),
    }),
  );
  await page.route(/\/api\/v1\/leads\/count/, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ total: FIXTURE_LEADS.length }),
    }),
  );
  await page.route(/\/api\/v1\/leads\/stats/, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        total: FIXTURE_LEADS.length,
        uncontacted: FIXTURE_LEADS.filter((l) =>
          ["discovered", "fingerprinted", "enriched"].includes(l.status),
        ).length,
        avg_score:
          FIXTURE_LEADS.reduce((s, l) => s + l.score, 0) / FIXTURE_LEADS.length,
        distinct_builders: new Set(
          FIXTURE_LEADS.map((l) => l.builder_detected).filter(
            (b) => b && b !== "unknown",
          ),
        ).size,
        distinct_sectors: new Set(FIXTURE_LEADS.map((l) => l.sector)).size,
        distinct_regions: new Set(FIXTURE_LEADS.map((l) => l.region)).size,
      }),
    }),
  );
  await page.route(/\/api\/v1\/projects(\?.*)?$/, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([FIXTURE_PROJECT]),
    }),
  );
  await page.route(/\/api\/v1\/projects\/1$/, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(FIXTURE_PROJECT),
    }),
  );
  await page.route(/\/api\/v1\/projects\/1\/phases/, (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  // Errors y residual-tasks vacíos por defecto.
  // /stats devuelve un objeto agregado; el listado, un array. Los
  // handlers específicos van DESPUÉS del catch-all para que Playwright
  // los priorice (último registrado gana).
  await page.route(/\/api\/v1\/errors(\?.*)?$/, (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.route(/\/api\/v1\/errors\/stats/, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        total: 0,
        critical: 0,
        error: 0,
        warning: 0,
        info: 0,
        debug: 0,
        distinct_components: 0,
        last_critical_at: null,
      }),
    }),
  );
  await page.route(/\/api\/v1\/residual-tasks(\?.*)?$/, (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.route(/\/api\/v1\/residual-tasks\/stats/, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        total: 0,
        open: 0,
        in_progress: 0,
        blocked: 0,
        done: 0,
        skipped: 0,
        blocking_go_live: 0,
        distinct_projects: 0,
        estimated_minutes_pending: 0,
      }),
    }),
  );
  // System info para /settings (v1.0.0). Health "ok" por defecto.
  await page.route(/\/api\/v1\/system\/info/, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        version: "1.0.0",
        environment: "test",
        python_version: "3.14.0",
        alembic_revision: "c8e1dc21716b",
        uptime_seconds: 123,
        health: {
          overall: "ok",
          db: "ok",
          redis: "ok",
          r2: "skipped",
        },
      }),
    }),
  );
}

/**
 * Helper para "iniciar sesión" en un test: añade la cookie wcm_session
 * directamente sin pasar por la UI de login. Útil cuando el flujo no
 * incluye el login y solo queremos verificar páginas internas.
 */
export async function loginViaCookie(page: Page, _baseURL = "http://127.0.0.1:3100"): Promise<void> {
  // Playwright addCookies requiere `url` SOLO (de donde infiere domain+path)
  // o bien `domain` + `path` juntos. Combinar `url` + `path` lanza:
  // "Cookie should have either url or path".
  await page.context().addCookies([
    {
      name: "wcm_session",
      value: "fake-jwt",
      domain: "127.0.0.1",
      path: "/",
      httpOnly: true,
    },
  ]);
}
