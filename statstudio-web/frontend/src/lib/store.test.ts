import { describe, it, expect, beforeEach } from "vitest";
import { store } from "./store";
import type { AnalysisRequest, AnalysisResult, DatasetPayload } from "./types";

const dataset: DatasetPayload = {
  name: "tiny",
  columns: [{ name: "x", type: "numeric" }, { name: "y", type: "numeric" }],
  rows: [{ x: 1, y: 2 }, { x: 3, y: 4 }],
  row_ids: ["a", "b"],
};

describe("store", () => {
  beforeEach(() => {
    store.set({ dataset: null, results: [], analyses: [], selection: new Set(), history: [],
                dashboards: [{ id: "dash-main", name: "Main dashboard", items: [] }],
                projectName: "Untitled project" });
  });

  it("starts empty", () => {
    expect(store.get().dataset).toBeNull();
    expect(store.get().selection.size).toBe(0);
  });

  it("sets dataset and toggles selection", () => {
    store.set({ dataset });
    expect(store.get().dataset?.name).toBe("tiny");
    store.toggleSelection("a");
    expect(store.get().selection.has("a")).toBe(true);
    store.toggleSelection("a");
    expect(store.get().selection.has("a")).toBe(false);
  });

  it("addResult logs an event", () => {
    const req: AnalysisRequest = { type: "descriptives", dataset, params: {}, options: {} };
    const res: AnalysisResult = {
      id: "r1", type: "descriptives", metadata: {}, statistical_tables: [],
      charts: [], textual_summary: "ok", warnings: [], reproducibility: {},
    };
    store.addResult(res, req);
    expect(store.get().results.length).toBe(1);
    expect(store.get().history.some((e) => e.kind === "analysis_run")).toBe(true);
  });

  it("roundtrip via toProject / loadProject", () => {
    store.set({ dataset, projectName: "p1" });
    const project = store.toProject();
    expect(project.datasets.length).toBe(1);
    expect(project.name).toBe("p1");
    store.set({ dataset: null });
    store.loadProject(project);
    expect(store.get().dataset?.name).toBe("tiny");
  });

  it("dashboard item add/remove", () => {
    store.addDashboardItem("dash-main", { kind: "chart", ref_id: "abc", title: "T" });
    const dash = store.get().dashboards[0];
    expect(dash.items.length).toBe(1);
    store.removeDashboardItem("dash-main", dash.items[0].id);
    expect(store.get().dashboards[0].items.length).toBe(0);
  });
});
