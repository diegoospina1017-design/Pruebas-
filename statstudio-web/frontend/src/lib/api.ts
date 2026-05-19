import type {
  AnalysisRequest, AnalysisResult, DatasetPayload, ProjectFile,
} from "./types";

const BASE = "/api";

async function jsonOr<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = (body && (body.detail || body.message)) || JSON.stringify(body);
    } catch { /* not json */ }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => fetch(`${BASE}/health`).then((r) => jsonOr<{ status: string; version: string }>(r)),

  importFile: (file: File): Promise<DatasetPayload> => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch(`${BASE}/files/import`, { method: "POST", body: fd }).then(jsonOr<DatasetPayload>);
  },

  previewFile: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch(`${BASE}/files/preview`, { method: "POST", body: fd })
      .then(jsonOr<{ columns: any[]; rows: any[]; row_ids: string[] }>);
  },

  exportCsv: async (payload: DatasetPayload) => {
    const r = await fetch(`${BASE}/files/export/csv`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error(`export csv: ${r.status}`);
    return r.blob();
  },

  exportXlsx: async (payload: DatasetPayload) => {
    const r = await fetch(`${BASE}/files/export/xlsx`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error(`export xlsx: ${r.status}`);
    return r.blob();
  },

  runAnalysis: (req: AnalysisRequest): Promise<AnalysisResult> =>
    fetch(`${BASE}/analyses/run`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(req),
    }).then(jsonOr<AnalysisResult>),

  cleanDataset: (body: {
    dataset: DatasetPayload;
    drop_missing?: boolean;
    impute_strategy?: "mean" | "median" | "mode" | null;
    columns?: string[];
    detect_outliers?: boolean;
    outlier_method?: "iqr" | "zscore";
  }) =>
    fetch(`${BASE}/datasets/clean`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }).then(jsonOr<{ dataset: DatasetPayload; summary: Record<string, any> }>),

  exportProjectJson: async (project: ProjectFile) => {
    const r = await fetch(`${BASE}/projects/export?fmt=json`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(project),
    });
    if (!r.ok) throw new Error(`export project: ${r.status}`);
    return r.blob();
  },

  importProjectFile: (file: File): Promise<ProjectFile> => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch(`${BASE}/projects/import`, { method: "POST", body: fd }).then(jsonOr<ProjectFile>);
  },

  exportHtmlReport: async (title: string, results: AnalysisResult[]) => {
    const r = await fetch(`${BASE}/reports/export/html`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ title, results }),
    });
    if (!r.ok) throw new Error(`html report: ${r.status}`);
    return r.text();
  },
};
