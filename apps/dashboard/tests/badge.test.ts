import { describe, expect, it } from "vitest";

import { statusVariant } from "../src/components/ui/badge";

describe("statusVariant", () => {
  it("mapea completed/done a success", () => {
    expect(statusVariant("completed")).toBe("success");
    expect(statusVariant("done")).toBe("success");
    expect(statusVariant("ready")).toBe("success");
  });

  it("mapea running/in_progress a default", () => {
    expect(statusVariant("running")).toBe("default");
    expect(statusVariant("in_progress")).toBe("default");
  });

  it("mapea blocked/qa_failed a warning", () => {
    expect(statusVariant("blocked_human_input")).toBe("warning");
    expect(statusVariant("qa_failed")).toBe("warning");
  });

  it("mapea failed/cancelled a danger", () => {
    expect(statusVariant("failed")).toBe("danger");
    expect(statusVariant("cancelled")).toBe("danger");
    expect(statusVariant("opted_out")).toBe("danger");
  });

  it("desconocidos a muted", () => {
    expect(statusVariant("zzz_unknown")).toBe("muted");
  });
});
