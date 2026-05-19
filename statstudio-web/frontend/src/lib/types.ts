// Shared types mirroring the backend pydantic schemas.

export type ColumnType =
  | "numeric" | "integer" | "categorical" | "boolean" | "datetime" | "text";

export interface ColumnMeta {
  name: string;
  type: ColumnType;
  nullable?: boolean;
  n_missing?: number;
  unique_count?: number;
  sample_values?: any[];
}

export interface DatasetPayload {
  name: string;
  columns: ColumnMeta[];
  rows: Record<string, any>[];
  row_ids?: string[];
}

export interface TableSpec {
  id: string;
  title: string;
  columns: string[];
  rows: any[][];
  notes?: string | null;
}

export interface ChartSpec {
  id: string;
  title: string;
  kind:
    | "histogram" | "boxplot" | "scatter" | "line" | "bar"
    | "qq" | "residuals" | "pareto" | "control" | "biplot"
    | "scree" | "heatmap" | "interaction" | "effects";
  data: any[];
  layout: Record<string, any>;
  row_ids?: string[] | null;
}

export type AnalysisType =
  | "descriptives"
  | "ttest_one_sample" | "ttest_two_sample" | "ttest_paired"
  | "chi_square" | "proportion_test"
  | "anova_one_way"
  | "regression_ols" | "regression_logistic"
  | "timeseries_summary" | "timeseries_forecast"
  | "control_chart_imr" | "control_chart_xbar_r"
  | "doe_factorial_design" | "doe_factorial_analyze"
  | "pca" | "kmeans" | "hclust";

export interface AnalysisRequest {
  type: AnalysisType;
  dataset: DatasetPayload;
  params: Record<string, any>;
  selection?: string[] | null;
  options?: Record<string, any>;
}

export interface AnalysisResult {
  id: string;
  type: AnalysisType;
  metadata: Record<string, any>;
  statistical_tables: TableSpec[];
  charts: ChartSpec[];
  textual_summary: string;
  warnings: string[];
  reproducibility: Record<string, any>;
}

export interface DashboardItem {
  id: string;
  kind: "chart" | "table" | "analysis";
  ref_id: string;
  x?: number; y?: number; w?: number; h?: number;
  title?: string;
}

export interface DashboardSpec {
  id: string;
  name: string;
  items: DashboardItem[];
}

export interface SessionEvent {
  id: string;
  kind: string;
  timestamp: string;
  payload: Record<string, any>;
}

export interface ProjectFile {
  schema_version: string;
  app_version: string;
  name: string;
  created_at: string;
  datasets: DatasetPayload[];
  dataset_meta: any[];
  analyses: AnalysisRequest[];
  results: AnalysisResult[];
  dashboards: DashboardSpec[];
  history: SessionEvent[];
  preferences: Record<string, any>;
}
