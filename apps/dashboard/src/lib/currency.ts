/**
 * Helpers de conversión EUR ↔ USD para inputs de coste en la UI.
 *
 * v0.27.0 — la API/BD trabaja en USD nativo (lo que factura OpenAI),
 * pero el operador es español y prefiere ver euros en el wizard. Esta
 * tasa es una aproximación — ajustar `NEXT_PUBLIC_EUR_USD_RATE` si EUR↔USD
 * se desvía >5% (típico cuando hay movimiento fuerte de divisas).
 *
 * Mayo 2026: 1 EUR ≈ 1.10 USD.
 */

const DEFAULT_EUR_USD_RATE = 1.1;

export function getEurUsdRate(): number {
  const raw = process.env.NEXT_PUBLIC_EUR_USD_RATE;
  if (!raw) return DEFAULT_EUR_USD_RATE;
  const parsed = Number.parseFloat(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_EUR_USD_RATE;
}

export function eurToUsd(eur: number): number {
  return eur * getEurUsdRate();
}

export function usdToEur(usd: number): number {
  return usd / getEurUsdRate();
}

export function formatEur(eur: number, fractionDigits = 2): string {
  return `${eur.toFixed(fractionDigits)} €`;
}

export function formatUsd(usd: number, fractionDigits = 2): string {
  return `$${usd.toFixed(fractionDigits)}`;
}
