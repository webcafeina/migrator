/**
 * Tests del helper currency (v0.27.0).
 */

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  eurToUsd,
  formatEur,
  formatUsd,
  getEurUsdRate,
  usdToEur,
} from "../src/lib/currency";

describe("getEurUsdRate", () => {
  const originalEnv = process.env.NEXT_PUBLIC_EUR_USD_RATE;

  afterEach(() => {
    if (originalEnv === undefined) {
      delete process.env.NEXT_PUBLIC_EUR_USD_RATE;
    } else {
      process.env.NEXT_PUBLIC_EUR_USD_RATE = originalEnv;
    }
  });

  it("default 1.10 sin env var", () => {
    delete process.env.NEXT_PUBLIC_EUR_USD_RATE;
    expect(getEurUsdRate()).toBe(1.1);
  });

  it("respeta NEXT_PUBLIC_EUR_USD_RATE válido", () => {
    process.env.NEXT_PUBLIC_EUR_USD_RATE = "1.15";
    expect(getEurUsdRate()).toBe(1.15);
  });

  it("ignora valor inválido (cae al default)", () => {
    process.env.NEXT_PUBLIC_EUR_USD_RATE = "abc";
    expect(getEurUsdRate()).toBe(1.1);
  });

  it("ignora valor 0 o negativo (cae al default)", () => {
    process.env.NEXT_PUBLIC_EUR_USD_RATE = "0";
    expect(getEurUsdRate()).toBe(1.1);
    process.env.NEXT_PUBLIC_EUR_USD_RATE = "-2";
    expect(getEurUsdRate()).toBe(1.1);
  });
});

describe("conversiones", () => {
  beforeEach(() => {
    delete process.env.NEXT_PUBLIC_EUR_USD_RATE;
  });

  it("eurToUsd default rate", () => {
    expect(eurToUsd(1)).toBeCloseTo(1.1, 5);
    expect(eurToUsd(0.9)).toBeCloseTo(0.99, 5);
  });

  it("usdToEur default rate", () => {
    expect(usdToEur(1.1)).toBeCloseTo(1.0, 5);
    expect(usdToEur(1.0)).toBeCloseTo(0.9091, 4);
  });
});

describe("formatters", () => {
  it("formatEur con 2 decimales default", () => {
    expect(formatEur(1)).toBe("1.00 €");
    expect(formatEur(0.95)).toBe("0.95 €");
  });

  it("formatUsd con 2 decimales default", () => {
    expect(formatUsd(1)).toBe("$1.00");
    expect(formatUsd(0.05)).toBe("$0.05");
  });

  it("respeta fractionDigits custom", () => {
    expect(formatEur(0.123, 4)).toBe("0.1230 €");
    expect(formatUsd(0.0005, 4)).toBe("$0.0005");
  });
});
