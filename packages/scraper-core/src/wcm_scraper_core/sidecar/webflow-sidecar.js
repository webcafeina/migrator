#!/usr/bin/env node
/**
 * webflow-sidecar.js
 *
 * Sidecar Node + Puppeteer especializado en cargar webs Webflow y esperar
 * correctamente a que `window.Webflow.ready()` haya completado, incluida
 * la inicialización de IX2 (Interactions 2.0). Playwright tiene problemas
 * conocidos con IX2 en algunos casos; Puppeteer resulta más fiable para
 * este vendor concreto.
 *
 * Invocado por `wcm_scraper_core.extractors.webflow` vía subprocess:
 *
 *   node webflow-sidecar.js --url=<url> [--proxy=<url>] [--ua=<ua>]
 *                            [--timeout-ms=30000] [--user-data-dir=<path>]
 *
 * Output (stdout): JSON con shape:
 *   {
 *     "html": "<html>...",
 *     "url": "https://...",
 *     "ix2_state": {...},          // estado serializable de IX2
 *     "page_timings": {...},
 *     "warnings": []
 *   }
 *
 * Códigos de salida:
 *   0 — éxito
 *   1 — timeout
 *   2 — error de red / 4xx/5xx
 *   3 — IX2 no detectado tras hidratación
 *   9 — error genérico
 */

"use strict";

const args = parseArgs(process.argv.slice(2));

const TARGET_URL = args["url"];
const PROXY = args["proxy"] || null;
const UA =
  args["ua"] ||
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36";
const TIMEOUT_MS = parseInt(args["timeout-ms"] || "30000", 10);

if (!TARGET_URL) {
  process.stderr.write("usage: node webflow-sidecar.js --url=<url> [opts]\n");
  process.exit(9);
}

(async () => {
  let puppeteer, StealthPlugin;
  try {
    puppeteer = require("puppeteer-extra");
    StealthPlugin = require("puppeteer-extra-plugin-stealth");
    puppeteer.use(StealthPlugin());
  } catch (e) {
    process.stderr.write(
      "Dependencies missing. Install with: npm install puppeteer-extra " +
        "puppeteer-extra-plugin-stealth puppeteer\n"
    );
    process.exit(9);
  }

  const launchArgs = ["--no-sandbox", "--disable-setuid-sandbox"];
  if (PROXY) launchArgs.push(`--proxy-server=${PROXY}`);

  let browser;
  try {
    browser = await puppeteer.launch({ headless: "new", args: launchArgs });
  } catch (e) {
    process.stderr.write(`launch failed: ${e.message}\n`);
    process.exit(9);
  }

  const warnings = [];

  try {
    const page = await browser.newPage();
    await page.setUserAgent(UA);
    await page.setViewport({ width: 1366, height: 900 });

    const response = await page.goto(TARGET_URL, {
      waitUntil: "networkidle2",
      timeout: TIMEOUT_MS,
    });
    if (!response) {
      warnings.push("response was null");
    } else if (response.status() >= 400) {
      process.stderr.write(`HTTP ${response.status()} for ${TARGET_URL}\n`);
      process.exit(2);
    }

    // Esperar Webflow.ready + settle IX2
    const ready = await page
      .waitForFunction(
        () => {
          return (
            typeof window.Webflow !== "undefined" &&
            Array.isArray(window.Webflow._ready) === false
          );
        },
        { timeout: TIMEOUT_MS }
      )
      .catch(() => false);

    if (!ready) {
      warnings.push("Webflow.ready no detectado — extractor degradará a heurística");
    }
    await sleep(1500);

    const html = await page.content();
    const ix2State = await page
      .evaluate(() => {
        try {
          if (!window.Webflow || !window.Webflow.ix2) return null;
          const store = window.Webflow.ix2.store;
          return store && typeof store.getState === "function"
            ? store.getState()
            : null;
        } catch (e) {
          return null;
        }
      })
      .catch(() => null);

    const timings = await page.evaluate(() => {
      const t = performance.timing || {};
      return {
        loadEventEnd: t.loadEventEnd,
        domContentLoadedEventEnd: t.domContentLoadedEventEnd,
        responseEnd: t.responseEnd,
        navigationStart: t.navigationStart,
      };
    });

    const out = {
      html,
      url: page.url(),
      ix2_state: ix2State,
      page_timings: timings,
      warnings,
    };

    process.stdout.write(JSON.stringify(out));
    await browser.close();
    process.exit(0);
  } catch (e) {
    if (browser) {
      try {
        await browser.close();
      } catch (_) {}
    }
    if (e && /timeout/i.test(String(e.message))) {
      process.stderr.write(`timeout: ${e.message}\n`);
      process.exit(1);
    }
    process.stderr.write(`error: ${e && e.message}\n`);
    process.exit(9);
  }
})();

function parseArgs(argv) {
  const out = {};
  for (const a of argv) {
    if (a.startsWith("--")) {
      const eq = a.indexOf("=");
      if (eq === -1) {
        out[a.slice(2)] = true;
      } else {
        out[a.slice(2, eq)] = a.slice(eq + 1);
      }
    }
  }
  return out;
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}
