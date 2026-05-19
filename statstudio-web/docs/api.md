# API REST — StatStudio Web

Base URL: `/api`. Todas las respuestas son JSON salvo donde se indica.

## Salud

`GET /api/health` → `{"status":"ok","version":"0.1.0"}`

## Archivos

### `POST /api/files/import` (multipart)
Importa un CSV o XLSX y devuelve un `DatasetPayload`.

```bash
curl -F "file=@samples/mtcars.csv" http://localhost:8000/api/files/import
```

### `POST /api/files/preview` (multipart)
Devuelve hasta 50 filas para vista previa.

### `POST /api/files/export/csv` y `POST /api/files/export/xlsx`
Body: `DatasetPayload`. Devuelve el archivo binario con `Content-Disposition`.

## Datasets

### `POST /api/datasets/summary`
Body: `DatasetPayload`. Devuelve missings por columna, dtypes pandas, columnas numéricas.

### `POST /api/datasets/clean`
```json
{
  "dataset": { "name": "x", "columns": [...], "rows": [...], "row_ids": [...] },
  "drop_missing": false,
  "impute_strategy": "median",
  "columns": ["age", "income"],
  "detect_outliers": true,
  "outlier_method": "iqr"
}
```
Respuesta: `{ "dataset": DatasetPayload, "summary": { "missing_before": {...}, "missing_after": {...}, "outliers": {...} } }`.

### `POST /api/datasets/pivot`
```json
{
  "dataset": DatasetPayload,
  "index": ["region"],
  "columns": ["product"],
  "values": "sales",
  "aggfunc": "sum"
}
```

## Análisis

### `GET /api/analyses/types`
Lista de tipos soportados.

### `POST /api/analyses/run`
Body genérico:

```json
{
  "type": "anova_one_way",
  "dataset": DatasetPayload,
  "params": { "response": "len", "factor": "supp" },
  "options": {}
}
```

Respuesta `AnalysisResult`:

```json
{
  "id": "uuid",
  "type": "anova_one_way",
  "metadata": { "params": {...}, "options": {...}, "dataset_name": "ToothGrowth" },
  "statistical_tables": [
    {
      "id": "uuid",
      "title": "One-way ANOVA: len ~ supp",
      "columns": ["source", "sum_sq", "df", "F", "p_value"],
      "rows": [["C(Q('supp'))", 205.35, 1.0, 4.0, 0.00231], ["Residual", 3246.86, 58.0, null, null]]
    }
  ],
  "charts": [
    {
      "id": "uuid",
      "title": "len by supp",
      "kind": "boxplot",
      "data": [ /* plotly traces */ ],
      "layout": { /* plotly layout */ },
      "row_ids": null
    }
  ],
  "textual_summary": "F=4.00, p=0.00231 across 2 groups.",
  "warnings": [],
  "reproducibility": { "app_version": "0.1.0", "timestamp": "...", "analysis_type": "anova_one_way", "params": {...} }
}
```

### Catálogo de `type` y `params` requeridos

| `type` | `params` |
| --- | --- |
| `descriptives` | `columns?: string[]`, `group_by?: string` |
| `ttest_one_sample` | `column`, `mu0`, `alternative` |
| `ttest_two_sample` | `value_column`, `group_column`, `equal_var`, `alternative` |
| `ttest_paired` | `column_a`, `column_b`, `alternative` |
| `chi_square` | `column_a`, `column_b` |
| `proportion_test` | `column`, `success_value`, opcional `group_column` o `p0` |
| `anova_one_way` | `response`, `factor` |
| `regression_ols` | `response`, `predictors[]` |
| `regression_logistic` | `response`, `predictors[]`, `positive_class?` |
| `timeseries_summary` | `value_column`, `time_column?`, `period?` |
| `timeseries_forecast` | `value_column`, `time_column?`, `method` (`ets`/`arima`), `horizon`, `period?`, `order?` |
| `control_chart_imr` | `column` |
| `control_chart_xbar_r` | `column`, `subgroup_column` |
| `doe_factorial_design` | `factors[{name, low, high}]`, `replicates`, `randomize`, `seed` |
| `doe_factorial_analyze` | `response`, `factors[]` |
| `pca` | `columns?`, `n_components`, `scale` |
| `kmeans` | `columns?`, `k`, `scale`, `seed` |
| `hclust` | `columns?`, `k`, `method`, `scale` |

## Proyectos

### `POST /api/projects/export?fmt=json|zip`
Body: `ProjectFile`. Devuelve un archivo descargable.

### `POST /api/projects/import` (multipart)
Body: `file` con `.statstudio.json` o `.statstudio.zip`. Devuelve `ProjectFile` ya migrado al esquema actual.

## Reportes

### `POST /api/reports/export/html`
```json
{ "title": "Mi reporte", "results": [AnalysisResult, ...] }
```
Devuelve un HTML autocontenido con tablas y charts Plotly (CDN).
