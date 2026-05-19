import { describe, it, expect } from "vitest";
import type { AnalysisRequest, ProjectFile } from "./types";

describe("serialization", () => {
  it("AnalysisRequest survives JSON roundtrip", () => {
    const req: AnalysisRequest = {
      type: "anova_one_way",
      dataset: { name: "x", columns: [{ name: "y", type: "numeric" }], rows: [{ y: 1 }], row_ids: ["r0"] },
      params: { response: "y", factor: "g" },
      options: { confidence: 0.95 },
    };
    const back = JSON.parse(JSON.stringify(req)) as AnalysisRequest;
    expect(back.type).toBe("anova_one_way");
    expect(back.params.response).toBe("y");
  });

  it("ProjectFile shape contains required fields", () => {
    const project: ProjectFile = {
      schema_version: "1.0.0",
      app_version: "0.1.0",
      name: "p",
      created_at: new Date().toISOString(),
      datasets: [],
      dataset_meta: [],
      analyses: [],
      results: [],
      dashboards: [],
      history: [],
      preferences: {},
    };
    const back = JSON.parse(JSON.stringify(project)) as ProjectFile;
    expect(back.schema_version).toBe("1.0.0");
  });
});
