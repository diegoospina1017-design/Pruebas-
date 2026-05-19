# StatStudio Web

Aplicación web de análisis estadístico estilo **Minitab** / **JMP**, con
**worksheet** tipo spreadsheet, **diálogos de análisis**, **ventana de
resultados con tablas y gráficos**, **historial reproducible**, **dashboards**
y **archivo de proyecto** guardable/reabrible.

```
┌────────────── Toolbar (Importar · Guardar · Reporte · Análisis ▾) ──────────────┐
│ Sidebar (datasets, columnas, proyectos, historial)                              │
│ ┌──────────────────────────────┬─────────────────────────────────────────────┐  │
│ │ Datos (AG Grid editable)      │ Resultados (cards + tablas + Plotly)       │  │
│ │ Dashboard (tiles arrastrables)│ Linked brushing entre grid y charts        │  │
│ └──────────────────────────────┴─────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Stack

| Capa       | Tecnología                                                     |
| ---------- | -------------------------------------------------------------- |
| Frontend   | Vite + React 18 + TypeScript + CSS Modules                     |
| Grid       | AG Grid Community 31                                           |
| Gráficos   | Plotly.js (linked brushing por `rowId` compartido)             |
| Persist.   | IndexedDB (idb)                                                |
| Backend    | FastAPI + pandas + SciPy + statsmodels + scikit-learn          |
| Excel      | openpyxl                                                       |
| Pruebas    | Vitest (frontend), pytest (backend), Playwright (E2E)          |
| DevOps     | Docker + docker-compose, GitHub Actions                        |

## Estructura del repositorio

```
statstudio-web/
  frontend/             # SPA (Vite + React + TS)
  backend/              # FastAPI app + servicios estadísticos
  samples/              # CSV de ejemplo (iris, mtcars, ToothGrowth, AirPassengers, USArrests, SPC, DOE)
  schemas/              # JSON Schemas (analysis-spec, project)
  docs/                 # Documentación (arquitectura, API)
  docker-compose.yml
```

## Comandos rápidos

### Desarrollo local

```bash
# 1) Backend
cd statstudio-web/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 2) Frontend (otra terminal)
cd statstudio-web/frontend
npm install
npm run dev               # http://localhost:5173 (proxy /api → :8000)
```

### Docker Compose

```bash
cd statstudio-web
docker compose up --build
# Frontend: http://localhost:8080
# Backend:  http://localhost:8000
```

### Pruebas

```bash
# Backend
cd statstudio-web/backend && pytest -q

# Frontend unit
cd statstudio-web/frontend && npm test -- --run

# E2E (Playwright) - requiere backend corriendo en :8000
cd statstudio-web/frontend
npm run test:e2e:install   # solo la primera vez
npm run test:e2e
```

## Funcionalidad implementada hoy (MVP real)

### Datos
- Importar CSV y XLSX (vista previa antes de importar; tamaño máx 50 MB).
- Exportar CSV / XLSX.
- Inferencia y corrección de tipos por columna (numeric, integer, categorical, boolean, datetime, text).
- Edición de celdas con undo/redo (AG Grid).
- Renombrado de columnas, **columna calculada** (sandbox: solo operadores aritméticos).
- Filtro/orden/búsqueda en grid (quick filter).
- Limpieza vía API: drop missing, imputación (mean/median/mode), detección de outliers (IQR/zscore).
- Pivot table básico (`POST /api/datasets/pivot`).

### Análisis
- Descriptivos (con `group_by`).
- t-tests (1 muestra, 2 muestras, pareada).
- Chi-cuadrado, prueba de proporciones (1 y 2 grupos).
- ANOVA one-way + Tukey HSD.
- Regresión OLS (univariante y múltiple) con residuos, Q-Q, fitted vs observed.
- Regresión logística binaria (coeficientes, OR, accuracy, AUC, ROC).
- Serie de tiempo: resumen + descomposición + ACF/PACF.
- Forecast univariante (ETS / ARIMA via statsmodels).
- Cartas de control I-MR y Xbar-R (constantes Shewhart D2/D3/D4/A2).
- DOE: generador 2^k con réplicas y aleatorización, análisis con efectos principales e interacciones.
- PCA (scree, scores, biplot).
- K-means y clustering jerárquico (Ward por defecto).

### UX
- Layout responsivo desktop-first: header + sidebar + main + paneles de resultados/dashboard.
- Toolbar de análisis con menú agrupado y desactivado sin dataset.
- **Linked brushing**: clic en puntos de un chart actualiza `selection` global y resalta filas en el grid; el grid propaga selección a charts.
- Dashboards con tiles añadidos desde Results; export HTML imprimible (`window.print()`).
- Drag & drop de archivos.
- Atajos: `Ctrl/Cmd+O` importar, `Ctrl/Cmd+S` guardar, `Ctrl/Cmd+P` reporte, `?` ayuda, `Esc` cerrar.
- Persistencia IndexedDB + descarga JSON de proyectos (`.statstudio.json`).
- Script Python reproducible incrustado en el `.statstudio.zip` (`reproduce.py`).

## Decisiones arquitectónicas clave

1. **Estadística en el backend** (Python). El frontend nunca calcula
   regresiones, ANOVA, PCA, etc. Esto centraliza la corrección numérica,
   simplifica el testing y permite reutilizar los mismos servicios desde
   scripts/notebooks.
2. **Resultados como contratos JSON** (`AnalysisResult`): tablas + charts +
   summary + warnings + reproducibility. El frontend solo renderiza.
3. **`rowId` estable**: cada fila importada recibe un identificador único
   que se propaga al backend en `dataset.row_ids` y vuelve en `chart.row_ids` /
   `chart.data[*].customdata`. Es lo que habilita brushing y selección
   coordinada.
4. **Persistencia en IndexedDB + archivo descargable**. Sin servidor de
   estado: el "proyecto" es un JSON. Versionado de esquema con migración.
5. **AG Grid Community + Plotly**. Cero features Enterprise; pivoting se hace
   en backend cuando hace falta.
6. **CSS Modules + variables CSS** en lugar de un framework pesado.
7. **Sandbox de columnas calculadas**: regex whitelist (`/^[\d+\-*/().\s eE]+$/`)
   tras sustituir referencias `${columna}`. **No** se ejecuta código del usuario.

## Extensiones futuras (módulos listos para extender)

- DOE: response surface (BBD/CCD), screening Plackett-Burman, optimización.
- Series de tiempo: SARIMA, Prophet, intervalos calibrados, validación rolling.
- Multivariante: MANOVA, LDA, mezcla de gaussianas, biplots avanzados.
- Cartas de control: P/NP, U/C, capability indices (Cp/Cpk/Pp/Ppk), reglas de Western Electric.
- Reporting: PowerPoint export (python-pptx), reportes parametrizados (Jinja2 templates).
- Auth + multiusuario + colaboración en tiempo real.
- Grid: pivots cliente para datasets pequeños, formato condicional, ediciones masivas.
- Workers: parsing CSV completo en cliente para datasets pequeños (`csv-parser.worker.ts` ya existe).

## Seguridad

- Validación de tipo/tamaño de archivo (CSV/XLSX/XLS; máx 50 MB).
- Sin `eval`: fórmulas en columnas calculadas se filtran con regex y se compilan con `new Function` solo sobre operadores aritméticos.
- Sin traceback crudo: errores de backend se mapean a `HTTP 400/500` con `detail` legible.
- CSP recomendada en producción (`script-src 'self' 'unsafe-inline'` solo si se usa `Plotly` con scripts inline; ver `frontend/nginx.conf` para endurecer).

## Licencias

Se prefieren dependencias permisivas (MIT/BSD/Apache-2.0). AG Grid Community es MIT; Plotly.js es MIT; pandas/SciPy/statsmodels/scikit-learn son BSD.

## Documentación adicional

- [`docs/architecture.md`](docs/architecture.md) — arquitectura, módulos y decisiones.
- [`docs/api.md`](docs/api.md) — endpoints REST y ejemplos de payload.
- [`schemas/analysis-spec.schema.json`](schemas/analysis-spec.schema.json), [`schemas/project.schema.json`](schemas/project.schema.json) — contratos JSON.
