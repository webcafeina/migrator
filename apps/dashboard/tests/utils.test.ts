import { describe, expect, it } from "vitest";

import { cn, formatDate, truncate } from "../src/lib/utils";

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("a", "b")).toBe("a b");
  });

  it("dedupes conflicting tailwind classes (last wins)", () => {
    expect(cn("p-2", "p-4")).toBe("p-4");
  });

  it("handles undefined/false gracefully", () => {
    expect(cn("a", undefined, false, null, "b")).toBe("a b");
  });
});

describe("formatDate", () => {
  it("returns em-dash for null/undefined/invalid", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate(undefined)).toBe("—");
    expect(formatDate("not a date")).toBe("—");
  });

  it("formats valid ISO date as dd/mm/yy hh:mm", () => {
    // Construir fecha local fija evita problemas de zona horaria en CI
    const d = new Date(2026, 4, 13, 14, 32); // 13 mayo 2026 14:32
    const out = formatDate(d.toISOString());
    expect(out).toMatch(/^\d{2}\/\d{2}\/\d{2} \d{2}:\d{2}$/);
  });
});

describe("truncate", () => {
  it("returns em-dash for empty/null", () => {
    expect(truncate(null, 10)).toBe("—");
    expect(truncate("", 10)).toBe("—");
  });

  it("returns original if shorter than limit", () => {
    expect(truncate("hola", 10)).toBe("hola");
  });

  it("truncates with ellipsis if longer than limit", () => {
    expect(truncate("hola mundo cruel", 10)).toBe("hola mund…");
  });
});
