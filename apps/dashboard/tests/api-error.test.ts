import { describe, expect, it } from "vitest";

import { ApiError } from "../src/lib/api";

describe("ApiError", () => {
  it("conserva status, code y details", () => {
    const e = new ApiError("oops", 404, "not_found", { who: "lead 42" });
    expect(e.status).toBe(404);
    expect(e.code).toBe("not_found");
    expect(e.details).toEqual({ who: "lead 42" });
    expect(e.message).toBe("oops");
  });

  it("instanceof Error", () => {
    const e = new ApiError("x", 500);
    expect(e).toBeInstanceOf(Error);
    expect(e).toBeInstanceOf(ApiError);
  });
});
