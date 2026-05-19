import { useState } from "react";
import { useStore, store } from "@/lib/store";
import { api } from "@/lib/api";
import type { AnalysisResult, ChartSpec, TableSpec } from "@/lib/types";
import { PlotlyChart } from "@/features/charts/PlotlyChart";
import styles from "./ResultsPanel.module.css";

export function ResultsPanel() {
  const results = useStore((s) => s.results);
  const analyses = useStore((s) => s.analyses);
  const [openIds, setOpenIds] = useState<Set<string>>(new Set());

  function toggle(id: string) {
    const next = new Set(openIds);
    next.has(id) ? next.delete(id) : next.add(id);
    setOpenIds(next);
  }

  if (results.length === 0) {
    return <div className={styles.empty}>Aún no hay análisis ejecutados.<br />Abre el menú <strong>Análisis</strong>.</div>;
  }

  return (
    <div className={styles.panel}>
      {results.slice().reverse().map((r, revIdx) => {
        const originalIdx = results.length - 1 - revIdx;
        const req = analyses[originalIdx];
        const isOpen = openIds.has(r.id) || revIdx === 0;
        return (
          <ResultCard key={r.id} result={r} req={req} expanded={isOpen} onToggle={() => toggle(r.id)} />
        );
      })}
    </div>
  );
}

function ResultCard({ result, req, expanded, onToggle }: {
  result: AnalysisResult;
  req: any;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <section className={styles.card} data-testid="result-card">
      <header onClick={onToggle}>
        <span className={styles.kind}>{result.type}</span>
        <h3>{result.statistical_tables[0]?.title || result.type}</h3>
        <small>{new Date(result.reproducibility?.timestamp ?? Date.now()).toLocaleTimeString()}</small>
      </header>
      {expanded && (
        <div className={styles.body}>
          <p className={styles.summary}>{result.textual_summary}</p>
          {result.warnings.length > 0 && (
            <ul className={styles.warnings}>
              {result.warnings.map((w, i) => <li key={i}>⚠ {w}</li>)}
            </ul>
          )}

          {result.statistical_tables.map((t) => <ResultTable key={t.id} table={t} />)}

          {result.charts.map((c) => (
            <div key={c.id} className={styles.chartBlock}>
              <div className={styles.chartHeader}>
                <strong>{c.title}</strong>
                <button onClick={() => store.addDashboardItem("dash-main", { kind: "chart", ref_id: `${result.id}:${c.id}`, title: c.title })}>
                  Añadir al dashboard
                </button>
              </div>
              <PlotlyChart spec={c} />
            </div>
          ))}

          <div className={styles.actions}>
            <button onClick={() => rerun(req)}>Re-ejecutar</button>
            <button onClick={() => exportSpec(result, req)}>Guardar spec</button>
            <button onClick={() => exportHtml([result], result.type)}>Exportar HTML</button>
            <button onClick={() => store.addDashboardItem("dash-main", { kind: "analysis", ref_id: result.id, title: result.type })}>
              Añadir todo al dashboard
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

function ResultTable({ table }: { table: TableSpec }) {
  return (
    <div className={styles.tableBlock}>
      <div className={styles.tableHeader}>
        <strong>{table.title}</strong>
        <button onClick={() => exportTableCsv(table)}>CSV</button>
      </div>
      <div className={styles.tableWrap}>
        <table>
          <thead><tr>{table.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>
            {table.rows.map((row, i) => (
              <tr key={i}>
                {row.map((c, j) => <td key={j}>{c === null || c === undefined ? "" : String(c)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

async function rerun(req: any) {
  if (!req) return;
  try {
    const res = await api.runAnalysis(req);
    store.addResult(res, req);
  } catch (e: any) {
    alert(`Error: ${e.message ?? e}`);
  }
}

function exportSpec(result: AnalysisResult, req: any) {
  const blob = new Blob([JSON.stringify({ request: req, result }, null, 2)], { type: "application/json" });
  download(blob, `${result.type}.spec.json`);
}

async function exportHtml(results: AnalysisResult[], title: string) {
  const html = await api.exportHtmlReport(title, results);
  const blob = new Blob([html], { type: "text/html" });
  download(blob, `${title}.html`);
}

function exportTableCsv(t: TableSpec) {
  const lines = [t.columns.join(",")];
  for (const row of t.rows) {
    lines.push(row.map((c) => csvCell(c)).join(","));
  }
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  download(blob, `${t.title.replace(/\s+/g, "_")}.csv`);
}

function csvCell(v: any): string {
  if (v == null) return "";
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}
