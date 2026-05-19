import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import { store, useStore } from "@/lib/store";
import type { AnalysisRequest, AnalysisType } from "@/lib/types";
import { numericColumns, categoricalColumns, columnNames } from "@/lib/columns";
import modal from "@/components/Modal.module.css";

export type DialogKey = AnalysisType;

const DIALOG_TITLES: Record<DialogKey, string> = {
  descriptives: "Estadística descriptiva",
  ttest_one_sample: "t-test (una muestra)",
  ttest_two_sample: "t-test (dos muestras)",
  ttest_paired: "t-test pareada",
  chi_square: "Chi-cuadrado",
  proportion_test: "Prueba de proporciones",
  anova_one_way: "ANOVA un factor",
  regression_ols: "Regresión OLS",
  regression_logistic: "Regresión logística",
  timeseries_summary: "Serie de tiempo (resumen)",
  timeseries_forecast: "Forecast univariante",
  control_chart_imr: "Carta de control I-MR",
  control_chart_xbar_r: "Carta de control Xbar-R",
  doe_factorial_design: "Diseño factorial 2^k",
  doe_factorial_analyze: "Análisis factorial",
  pca: "Análisis de componentes principales",
  kmeans: "K-means",
  hclust: "Cluster jerárquico",
};

export function AnalysisDialogs({ which, onClose }: { which: DialogKey; onClose: () => void }) {
  const dataset = useStore((s) => s.dataset);
  const [params, setParams] = useState<Record<string, any>>(() => defaultParams(which, dataset));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const numCols = useMemo(() => dataset ? numericColumns(dataset).map((c) => c.name) : [], [dataset]);
  const catCols = useMemo(() => dataset ? categoricalColumns(dataset).map((c) => c.name) : [], [dataset]);
  const allCols = useMemo(() => dataset ? columnNames(dataset) : [], [dataset]);

  function setParam(k: string, v: any) { setParams((p) => ({ ...p, [k]: v })); }

  async function run() {
    if (!dataset) return;
    setBusy(true);
    setError(null);
    try {
      const req: AnalysisRequest = {
        type: which,
        dataset,
        params,
        options: {},
      };
      const res = await api.runAnalysis(req);
      store.addResult(res, req);
      onClose();
    } catch (e: any) {
      setError(e.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={modal.backdrop} onClick={onClose}>
      <div className={modal.modal} onClick={(e) => e.stopPropagation()}>
        <header><h3>{DIALOG_TITLES[which]}</h3><button onClick={onClose}>×</button></header>
        <div className={modal.body}>
          {renderForm(which, params, setParam, { numCols, catCols, allCols })}
        </div>
        {error && <div className={modal.error}>{error}</div>}
        <div className={modal.footer}>
          <button onClick={onClose}>Cancelar</button>
          <button className="primary" onClick={run} disabled={busy || !dataset} data-testid="run-analysis">
            {busy ? "Ejecutando…" : "Ejecutar"}
          </button>
        </div>
      </div>
    </div>
  );
}

function defaultParams(which: DialogKey, ds: any): Record<string, any> {
  if (!ds) return {};
  const numeric = ds.columns.filter((c: any) => c.type === "numeric" || c.type === "integer").map((c: any) => c.name);
  const cat = ds.columns.filter((c: any) => c.type === "categorical" || c.type === "boolean" || c.type === "text").map((c: any) => c.name);
  switch (which) {
    case "descriptives": return { columns: numeric };
    case "ttest_one_sample": return { column: numeric[0], mu0: 0, alternative: "two-sided" };
    case "ttest_two_sample": return { value_column: numeric[0], group_column: cat[0], equal_var: false, alternative: "two-sided" };
    case "ttest_paired": return { column_a: numeric[0], column_b: numeric[1], alternative: "two-sided" };
    case "chi_square": return { column_a: cat[0], column_b: cat[1] };
    case "proportion_test": return { column: cat[0], success_value: "", group_column: "", p0: 0.5, alternative: "two-sided" };
    case "anova_one_way": return { response: numeric[0], factor: cat[0] };
    case "regression_ols": return { response: numeric[0], predictors: numeric.slice(1, 3) };
    case "regression_logistic": return { response: cat[0] || numeric[0], predictors: numeric.slice(0, 2), positive_class: "" };
    case "timeseries_summary": return { value_column: numeric[0], time_column: "", period: 12 };
    case "timeseries_forecast": return { value_column: numeric[0], time_column: "", method: "ets", horizon: 12, period: 12 };
    case "control_chart_imr": return { column: numeric[0] };
    case "control_chart_xbar_r": return { column: numeric[0], subgroup_column: cat[0] || numeric[1] };
    case "doe_factorial_design": return {
      factors: [
        { name: "A", low: -1, high: 1 },
        { name: "B", low: -1, high: 1 },
      ],
      replicates: 2,
      randomize: true,
      seed: 42,
    };
    case "doe_factorial_analyze": return { response: numeric[0], factors: numeric.slice(1, 4) };
    case "pca": return { columns: numeric, n_components: Math.min(3, numeric.length), scale: true };
    case "kmeans": return { columns: numeric, k: 3, scale: true, seed: 42 };
    case "hclust": return { columns: numeric, k: 3, method: "ward", scale: true };
    default: return {};
  }
}

interface FormCtx {
  numCols: string[];
  catCols: string[];
  allCols: string[];
}

function renderForm(
  which: DialogKey, params: Record<string, any>, setP: (k: string, v: any) => void, ctx: FormCtx,
) {
  switch (which) {
    case "descriptives": return <>
      <MultiSelect label="Variables" value={params.columns ?? []} options={ctx.numCols} onChange={(v) => setP("columns", v)} />
      <SelectField label="Agrupar por (opcional)" value={params.group_by ?? ""} options={["", ...ctx.catCols]} onChange={(v) => setP("group_by", v || null)} />
    </>;
    case "ttest_one_sample": return <>
      <SelectField label="Columna" value={params.column} options={ctx.numCols} onChange={(v) => setP("column", v)} />
      <NumberField label="mu0" value={params.mu0} onChange={(v) => setP("mu0", v)} />
      <SelectField label="Alternativa" value={params.alternative} options={["two-sided", "less", "greater"]} onChange={(v) => setP("alternative", v)} />
    </>;
    case "ttest_two_sample": return <>
      <SelectField label="Respuesta (num)" value={params.value_column} options={ctx.numCols} onChange={(v) => setP("value_column", v)} />
      <SelectField label="Grupo (cat)" value={params.group_column} options={ctx.catCols.length ? ctx.catCols : ctx.allCols} onChange={(v) => setP("group_column", v)} />
      <CheckField label="Varianzas iguales" value={!!params.equal_var} onChange={(v) => setP("equal_var", v)} />
      <SelectField label="Alternativa" value={params.alternative} options={["two-sided", "less", "greater"]} onChange={(v) => setP("alternative", v)} />
    </>;
    case "ttest_paired": return <>
      <SelectField label="Columna A" value={params.column_a} options={ctx.numCols} onChange={(v) => setP("column_a", v)} />
      <SelectField label="Columna B" value={params.column_b} options={ctx.numCols} onChange={(v) => setP("column_b", v)} />
      <SelectField label="Alternativa" value={params.alternative} options={["two-sided", "less", "greater"]} onChange={(v) => setP("alternative", v)} />
    </>;
    case "chi_square": return <>
      <SelectField label="Columna A" value={params.column_a} options={ctx.allCols} onChange={(v) => setP("column_a", v)} />
      <SelectField label="Columna B" value={params.column_b} options={ctx.allCols} onChange={(v) => setP("column_b", v)} />
    </>;
    case "proportion_test": return <>
      <SelectField label="Columna" value={params.column} options={ctx.allCols} onChange={(v) => setP("column", v)} />
      <TextField label="Valor de éxito" value={params.success_value ?? ""} onChange={(v) => setP("success_value", v)} />
      <SelectField label="Columna de grupo (opcional)" value={params.group_column ?? ""} options={["", ...ctx.catCols]} onChange={(v) => setP("group_column", v || null)} />
      {!params.group_column && <NumberField label="p0" value={params.p0 ?? 0.5} onChange={(v) => setP("p0", v)} />}
    </>;
    case "anova_one_way": return <>
      <SelectField label="Respuesta (num)" value={params.response} options={ctx.numCols} onChange={(v) => setP("response", v)} />
      <SelectField label="Factor (cat)" value={params.factor} options={ctx.allCols} onChange={(v) => setP("factor", v)} />
    </>;
    case "regression_ols": return <>
      <SelectField label="Respuesta (num)" value={params.response} options={ctx.numCols} onChange={(v) => setP("response", v)} />
      <MultiSelect label="Predictores" value={params.predictors ?? []} options={ctx.allCols.filter((c) => c !== params.response)} onChange={(v) => setP("predictors", v)} />
    </>;
    case "regression_logistic": return <>
      <SelectField label="Respuesta (binaria)" value={params.response} options={ctx.allCols} onChange={(v) => setP("response", v)} />
      <MultiSelect label="Predictores" value={params.predictors ?? []} options={ctx.allCols.filter((c) => c !== params.response)} onChange={(v) => setP("predictors", v)} />
      <TextField label="Clase positiva" value={params.positive_class ?? ""} onChange={(v) => setP("positive_class", v)} />
    </>;
    case "timeseries_summary":
    case "timeseries_forecast": return <>
      <SelectField label="Columna (valor)" value={params.value_column} options={ctx.numCols} onChange={(v) => setP("value_column", v)} />
      <SelectField label="Columna (tiempo)" value={params.time_column ?? ""} options={["", ...ctx.allCols]} onChange={(v) => setP("time_column", v || null)} />
      <NumberField label="Periodo (estacional)" value={params.period ?? 12} onChange={(v) => setP("period", v)} />
      {which === "timeseries_forecast" && <>
        <SelectField label="Método" value={params.method ?? "ets"} options={["ets", "arima"]} onChange={(v) => setP("method", v)} />
        <NumberField label="Horizonte" value={params.horizon ?? 12} onChange={(v) => setP("horizon", v)} />
      </>}
    </>;
    case "control_chart_imr": return <>
      <SelectField label="Columna" value={params.column} options={ctx.numCols} onChange={(v) => setP("column", v)} />
    </>;
    case "control_chart_xbar_r": return <>
      <SelectField label="Columna (valor)" value={params.column} options={ctx.numCols} onChange={(v) => setP("column", v)} />
      <SelectField label="Subgrupo" value={params.subgroup_column} options={ctx.allCols} onChange={(v) => setP("subgroup_column", v)} />
    </>;
    case "doe_factorial_design": return <FactorialEditor params={params} setP={setP} />;
    case "doe_factorial_analyze": return <>
      <SelectField label="Respuesta" value={params.response} options={ctx.numCols} onChange={(v) => setP("response", v)} />
      <MultiSelect label="Factores (2 niveles)" value={params.factors ?? []} options={ctx.allCols.filter((c) => c !== params.response)} onChange={(v) => setP("factors", v)} />
    </>;
    case "pca": return <>
      <MultiSelect label="Variables" value={params.columns ?? []} options={ctx.numCols} onChange={(v) => setP("columns", v)} />
      <NumberField label="N componentes" value={params.n_components ?? 2} onChange={(v) => setP("n_components", v)} />
      <CheckField label="Estandarizar" value={params.scale ?? true} onChange={(v) => setP("scale", v)} />
    </>;
    case "kmeans": return <>
      <MultiSelect label="Variables" value={params.columns ?? []} options={ctx.numCols} onChange={(v) => setP("columns", v)} />
      <NumberField label="k" value={params.k ?? 3} onChange={(v) => setP("k", v)} />
      <CheckField label="Estandarizar" value={params.scale ?? true} onChange={(v) => setP("scale", v)} />
      <NumberField label="seed" value={params.seed ?? 42} onChange={(v) => setP("seed", v)} />
    </>;
    case "hclust": return <>
      <MultiSelect label="Variables" value={params.columns ?? []} options={ctx.numCols} onChange={(v) => setP("columns", v)} />
      <NumberField label="k" value={params.k ?? 3} onChange={(v) => setP("k", v)} />
      <SelectField label="Método" value={params.method ?? "ward"} options={["ward", "single", "complete", "average"]} onChange={(v) => setP("method", v)} />
      <CheckField label="Estandarizar" value={params.scale ?? true} onChange={(v) => setP("scale", v)} />
    </>;
    default: return null;
  }
}

function SelectField({ label, value, options, onChange }: { label: string; value: any; options: string[]; onChange: (v: string) => void }) {
  return (
    <div className={modal.formRow}>
      <label>{label}</label>
      <select value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => <option key={o} value={o}>{o || "—"}</option>)}
      </select>
    </div>
  );
}

function MultiSelect({ label, value, options, onChange }: { label: string; value: string[]; options: string[]; onChange: (v: string[]) => void }) {
  return (
    <div className={modal.formRow}>
      <label>{label}</label>
      <select multiple size={Math.min(8, Math.max(3, options.length))}
              value={value} style={{ flex: 1, minHeight: 90 }}
              onChange={(e) => onChange(Array.from(e.target.selectedOptions, (o) => o.value))}>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div className={modal.formRow}>
      <label>{label}</label>
      <input type="number" value={value ?? 0} onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  );
}
function TextField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className={modal.formRow}>
      <label>{label}</label>
      <input type="text" value={value ?? ""} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}
function CheckField({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className={modal.formRow}>
      <label>{label}</label>
      <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} />
    </div>
  );
}

function FactorialEditor({ params, setP }: { params: any; setP: (k: string, v: any) => void }) {
  const factors = params.factors ?? [];
  const update = (i: number, key: string, v: any) => {
    const next = factors.map((f: any, idx: number) => (idx === i ? { ...f, [key]: v } : f));
    setP("factors", next);
  };
  return (
    <>
      {factors.map((f: any, i: number) => (
        <div className={modal.formRow} key={i}>
          <label>Factor {i + 1}</label>
          <input value={f.name} onChange={(e) => update(i, "name", e.target.value)} style={{ flex: "0 0 80px" }} />
          <input type="number" value={f.low} onChange={(e) => update(i, "low", Number(e.target.value))} style={{ flex: "0 0 80px" }} />
          <input type="number" value={f.high} onChange={(e) => update(i, "high", Number(e.target.value))} style={{ flex: "0 0 80px" }} />
          <button onClick={() => setP("factors", factors.filter((_: any, idx: number) => idx !== i))}>x</button>
        </div>
      ))}
      <div className={modal.formRow}>
        <label></label>
        <button onClick={() => setP("factors", [...factors, { name: `F${factors.length + 1}`, low: -1, high: 1 }])}>
          + factor
        </button>
      </div>
      <NumberField label="Réplicas" value={params.replicates ?? 1} onChange={(v) => setP("replicates", v)} />
      <CheckField label="Aleatorizar" value={params.randomize ?? true} onChange={(v) => setP("randomize", v)} />
      <NumberField label="Seed" value={params.seed ?? 42} onChange={(v) => setP("seed", v)} />
    </>
  );
}
