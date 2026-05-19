import { useMemo } from "react";
import { store, useStore } from "@/lib/store";
import { PlotlyChart } from "@/features/charts/PlotlyChart";
import type { ChartSpec, TableSpec } from "@/lib/types";
import styles from "./DashboardView.module.css";

export function DashboardView() {
  const dashboards = useStore((s) => s.dashboards);
  const results = useStore((s) => s.results);
  const dash = dashboards[0];

  const charts = useMemo(() => {
    const map = new Map<string, ChartSpec & { resultId: string }>();
    for (const r of results) for (const c of r.charts) map.set(`${r.id}:${c.id}`, { ...c, resultId: r.id });
    return map;
  }, [results]);

  const tables = useMemo(() => {
    const map = new Map<string, TableSpec & { resultId: string }>();
    for (const r of results) for (const t of r.statistical_tables) map.set(`${r.id}:${t.id}`, { ...t, resultId: r.id });
    return map;
  }, [results]);

  if (!dash || dash.items.length === 0) {
    return <div className={styles.empty}>Dashboard vacío. Añade gráficos desde la pestaña Resultados.</div>;
  }

  return (
    <div className={styles.grid}>
      {dash.items.map((it) => {
        let body: any = null;
        let title = it.title || it.ref_id;
        if (it.kind === "chart") {
          const spec = charts.get(it.ref_id);
          if (spec) { body = <PlotlyChart spec={spec} height={300} />; title = spec.title; }
        } else if (it.kind === "table") {
          const t = tables.get(it.ref_id);
          if (t) body = <MiniTable table={t} />;
        } else if (it.kind === "analysis") {
          const r = results.find((rr) => rr.id === it.ref_id);
          if (r) {
            body = (
              <div className={styles.analysisBlock}>
                <p className={styles.summary}>{r.textual_summary}</p>
                {r.charts.slice(0, 1).map((c) => <PlotlyChart key={c.id} spec={c} height={260} />)}
              </div>
            );
            title = `${r.type} - ${r.id.slice(0, 6)}`;
          }
        }
        return (
          <div className={styles.tile} key={it.id}>
            <header>
              <strong>{title}</strong>
              <button onClick={() => store.removeDashboardItem(dash.id, it.id)}>×</button>
            </header>
            <div className={styles.tileBody}>{body ?? <em>(elemento no encontrado)</em>}</div>
          </div>
        );
      })}
    </div>
  );
}

function MiniTable({ table }: { table: TableSpec }) {
  return (
    <div style={{ maxHeight: 260, overflow: "auto" }}>
      <table>
        <thead><tr>{table.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>
          {table.rows.map((row, i) => (
            <tr key={i}>{row.map((c, j) => <td key={j}>{c == null ? "" : String(c)}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
