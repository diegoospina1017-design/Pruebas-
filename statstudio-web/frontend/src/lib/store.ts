// Minimal observable store - tiny pub/sub so we avoid pulling in a state lib.
import { useEffect, useState } from "react";

import type {
  AnalysisRequest, AnalysisResult, DashboardSpec, DatasetPayload,
  ProjectFile, SessionEvent,
} from "./types";

export interface AppState {
  dataset: DatasetPayload | null;
  results: AnalysisResult[];
  analyses: AnalysisRequest[];
  selection: Set<string>; // selected row_ids
  dashboards: DashboardSpec[];
  history: SessionEvent[];
  projectName: string;
}

type Listener = (s: AppState) => void;

class Store {
  private state: AppState = {
    dataset: null,
    results: [],
    analyses: [],
    selection: new Set(),
    dashboards: [{ id: "dash-main", name: "Main dashboard", items: [] }],
    history: [],
    projectName: "Untitled project",
  };
  private listeners: Set<Listener> = new Set();

  get(): AppState { return this.state; }

  set(updater: Partial<AppState> | ((s: AppState) => Partial<AppState>)) {
    const patch = typeof updater === "function" ? updater(this.state) : updater;
    this.state = { ...this.state, ...patch };
    this.listeners.forEach((l) => l(this.state));
  }

  subscribe(l: Listener): () => void {
    this.listeners.add(l);
    return () => this.listeners.delete(l);
  }

  logEvent(kind: string, payload: Record<string, any> = {}) {
    const evt: SessionEvent = {
      id: crypto.randomUUID(),
      kind,
      timestamp: new Date().toISOString(),
      payload,
    };
    this.set({ history: [...this.state.history, evt] });
  }

  setSelection(ids: Iterable<string>) {
    this.set({ selection: new Set(ids) });
  }

  toggleSelection(id: string) {
    const next = new Set(this.state.selection);
    if (next.has(id)) next.delete(id); else next.add(id);
    this.set({ selection: next });
  }

  clearSelection() { this.set({ selection: new Set() }); }

  addResult(r: AnalysisResult, req: AnalysisRequest) {
    this.set({
      results: [...this.state.results, r],
      analyses: [...this.state.analyses, req],
    });
    this.logEvent("analysis_run", { id: r.id, type: r.type });
  }

  addDashboardItem(dashId: string, item: { kind: "chart"|"table"|"analysis"; ref_id: string; title?: string }) {
    const dashboards = this.state.dashboards.map((d) =>
      d.id === dashId
        ? { ...d, items: [...d.items, { id: crypto.randomUUID(), w: 6, h: 4, x: 0, y: 0, ...item }] }
        : d
    );
    this.set({ dashboards });
    this.logEvent("dashboard_add", { dashboard: dashId, ...item });
  }

  removeDashboardItem(dashId: string, itemId: string) {
    const dashboards = this.state.dashboards.map((d) =>
      d.id === dashId ? { ...d, items: d.items.filter((i) => i.id !== itemId) } : d
    );
    this.set({ dashboards });
  }

  loadProject(p: ProjectFile) {
    this.state = {
      dataset: p.datasets[0] ?? null,
      results: p.results ?? [],
      analyses: p.analyses ?? [],
      selection: new Set(),
      dashboards: p.dashboards?.length ? p.dashboards : [{ id: "dash-main", name: "Main", items: [] }],
      history: p.history ?? [],
      projectName: p.name,
    };
    this.listeners.forEach((l) => l(this.state));
    this.logEvent("project_loaded", { name: p.name });
  }

  toProject(): ProjectFile {
    return {
      schema_version: "1.0.0",
      app_version: "0.1.0",
      name: this.state.projectName,
      created_at: new Date().toISOString(),
      datasets: this.state.dataset ? [this.state.dataset] : [],
      dataset_meta: [],
      analyses: this.state.analyses,
      results: this.state.results,
      dashboards: this.state.dashboards,
      history: this.state.history,
      preferences: {},
    };
  }
}

export const store = new Store();

export function useStore<T>(selector: (s: AppState) => T): T {
  const [value, setValue] = useState<T>(() => selector(store.get()));
  useEffect(() => {
    return store.subscribe((s) => setValue(selector(s)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return value;
}
