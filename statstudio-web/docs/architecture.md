# Arquitectura — StatStudio Web

## Visión general

StatStudio Web es un cliente SPA que delega todo el cálculo estadístico a un
servicio HTTP. El frontend mantiene el estado de sesión (dataset, resultados,
selección, dashboards) en memoria y persiste en IndexedDB; al usuario se le
expone un archivo de proyecto descargable (`.statstudio.json` /
`.statstudio.zip`) que es la unidad de portabilidad.

```
┌─────────────────────────── Frontend (Vite + React + TS) ───────────────────────────┐
│                                                                                    │
│  ┌─ Toolbar ─────────────────────────────────────────────────────────────────┐    │
│  │  Importar | Guardar | Reporte | Análisis ▾ |  Datos · Resultados · Dash   │    │
│  └────────────────────────────────────────────────────────────────────────────┘    │
│  ┌─ Sidebar ─┐  ┌─ Main view ─────────────────────────────────────────────────┐   │
│  │ Dataset   │  │ DataGridView   ResultsPanel   DashboardView                 │   │
│  │ Columns   │  │     (AG Grid)   (cards + Plotly + tablas)                   │   │
│  │ Projects  │  │                                                              │   │
│  │ History   │  └──────────────────────────────────────────────────────────────┘   │
│  └───────────┘                                                                     │
│                                                                                    │
│  Store (pub/sub):  dataset · selection · results · dashboards · history            │
│  Persistence:      IndexedDB (`idb`)                                               │
└──────────────────────────────────────┬─────────────────────────────────────────────┘
                                       │ JSON over HTTP (`/api/*`)
┌──────────────────────────────────────▼─────────────────────────────────────────────┐
│ Backend (FastAPI · Python 3.12)                                                    │
│                                                                                    │
│  api/routes/{files,datasets,analyses,projects,reports}.py    schemas/ (pydantic)   │
│  services/                                                                         │
│    analysis/  descriptives, hypothesis, anova, regression,                         │
│               timeseries, control_charts, doe, multivariate                        │
│    datasets/  import_export, cleaning                                              │
│    projects/  project_io  (json + zip + reproducibility script)                    │
│    reporting/ html_report                                                          │
│  utils/dataframe.py:  DatasetPayload  ⇄  pandas.DataFrame                          │
└────────────────────────────────────────────────────────────────────────────────────┘
```

## Frontend

### Capas
- `lib/types.ts` — TS mirror de los `pydantic` schemas.
- `lib/api.ts` — fetch wrapper, sin estado.
- `lib/store.ts` — pub/sub minimalista (60 LOC). Evita Redux/Zustand para mantener el bundle pequeño y la lectura simple.
- `lib/idb.ts` — IndexedDB; objectStores `projects` y `kv`.
- `lib/columns.ts` — utilidades de inspección de columnas.

### Features
- `data-grid/` — AG Grid con tipos editables, undo/redo, columnas calculadas (sandbox aritmético), exportación.
- `import-export/ImportDialog.tsx` — drag & drop + preview + import.
- `analysis-dialogs/AnalysisDialogs.tsx` — un solo componente que renderiza el formulario correcto por tipo de análisis. Defaults inteligentes según columnas numéricas/categóricas.
- `results/ResultsPanel.tsx` — cards plegables con tablas, charts y acciones (re-ejecutar, exportar spec, HTML, añadir al dashboard).
- `charts/PlotlyChart.tsx` — wrapper Plotly con linked brushing: lee `selection` del store y aplica estilo a puntos con `customdata` (`row_id`).
- `dashboards/DashboardView.tsx` — grilla de tiles persistida en proyecto.

### Linked brushing
1. Cada chart con datos por fila incluye `customdata = row_ids` en sus traces.
2. El usuario hace click o selección rectangular en Plotly → el handler agrega los IDs al `store.selection`.
3. El grid usa `getRowId` para mapear, y `PlotlyChart` re-renderiza con `marker.size/color` resaltado.
4. Resultado: grid ↔ todos los charts ↔ tabla de resultados comparten el mismo conjunto de `row_id`.

## Backend

### Contrato común
Todas las funciones de análisis comparten la firma `(req: AnalysisRequest) -> AnalysisResult`. `make_result` en `services/analysis/_common.py`:
- Genera un UUID.
- Sanea valores numpy a tipos Python (clave para que Pydantic serialize NumPy `int64`/`float64`).
- Adjunta `reproducibility` (versión, timestamp, params, options).

### Datos
`DatasetPayload` ⇄ `pandas.DataFrame` con `payload_to_df` / `df_to_payload`. El `row_id` se conserva como `index.name = "row_id"`; los análisis que producen scatter/regresión propagan `row_ids` a los traces para habilitar brushing.

### Reproducibilidad
- Cada análisis se persiste como **request** (`AnalysisRequest`) y **result** (`AnalysisResult`) en el proyecto. El request es el "analysis spec" que basta para reproducir.
- `project_io.export_project_zip` produce `.statstudio.zip` con `project.json`, `datasets/*.csv` y un `reproduce.py` autogenerado que invoca `/api/analyses/run` para cada spec.
- Versionado de esquema: `schema_version` en `ProjectFile`; `_migrate` aplica upgrades futuros.

### Cartas de control
Constantes Shewhart (D2, D3, D4, A2) en tabla; tamaño de subgrupo 2..10 soportado en `Xbar-R`. Para `I-MR`, σ ≈ MR̄/d2 (n=2).

### DOE
Análisis ajusta un OLS con todos los términos principales + interacciones de 2 vías. Las dos columnas con 2 niveles distintos se mapean a -1/+1; las numéricas con más niveles se estandarizan.

## Decisiones técnicas

| Decisión | Por qué |
| --- | --- |
| Cálculo en backend | Corrección numérica, librerías maduras (statsmodels/SciPy), reutilizable desde scripts. |
| AG Grid Community | Spreadsheet madura, MIT, edición y undo/redo built-in. |
| Plotly.js | Coberturas de chart amplia, soporte de `selectedpoints` y `customdata` para brushing. |
| CSS Modules | Cero dependencias de framework; estilos coherentes vía variables CSS. |
| Pub/sub propio | El store es pequeño; evita peso de Redux/Zustand. |
| FastAPI | Tipado fuerte vía Pydantic, OpenAPI gratis. |
| Sanitización en `make_result` | Pydantic v2 no serializa `numpy.int64`/`float64` por defecto. |

## Datos de prueba

`samples/` contiene réplicas (sintéticas o exactas) de datasets clásicos R:
- `iris.csv` (3 especies, 50 obs c/u)
- `mtcars.csv` (32 autos)
- `ToothGrowth.csv` (60 obs balanceadas)
- `AirPassengers.csv` (mensual 1949-1960)
- `USArrests.csv` (50 estados)
- `spc_bottling.csv` (25 subgrupos × 5)
- `doe_factorial_2k.csv` (2³ con 2 réplicas)
