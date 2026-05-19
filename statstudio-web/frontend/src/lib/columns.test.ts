import { describe, it, expect } from "vitest";
import { inferTypeFromValues, numericColumns, categoricalColumns } from "./columns";

describe("inferTypeFromValues", () => {
  it("detects integers", () => {
    expect(inferTypeFromValues([1, 2, 3, 4, 5])).toBe("integer");
  });
  it("detects numerics", () => {
    expect(inferTypeFromValues([1.2, 2.5, 3.7])).toBe("numeric");
  });
  it("detects categorical for low cardinality strings", () => {
    expect(inferTypeFromValues(["A", "B", "A", "B", "A"])).toBe("categorical");
  });
  it("detects text for high cardinality strings", () => {
    expect(inferTypeFromValues(Array.from({ length: 50 }, (_, i) => `s${i}`))).toBe("text");
  });
  it("handles empty input as text", () => {
    expect(inferTypeFromValues([null, undefined, ""])).toBe("text");
  });
});

describe("column selectors", () => {
  const ds = {
    name: "x",
    columns: [
      { name: "a", type: "numeric" as const },
      { name: "b", type: "integer" as const },
      { name: "c", type: "categorical" as const },
    ],
    rows: [],
  };
  it("filters numeric", () => {
    expect(numericColumns(ds).map((c) => c.name)).toEqual(["a", "b"]);
  });
  it("filters categorical", () => {
    expect(categoricalColumns(ds).map((c) => c.name)).toEqual(["c"]);
  });
});
