import { useEffect, useState } from "react";
import { useStore, store } from "@/lib/store";
import { idb } from "@/lib/idb";
import { api } from "@/lib/api";
import styles from "./Sidebar.module.css";

export function Sidebar() {
  const dataset = useStore((s) => s.dataset);
  const history = useStore((s) => s.history);
  const results = useStore((s) => s.results);
  const [saved, setSaved] = useState<{ name: string; updated_at: string }[]>([]);

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    const list = await idb.listProjects();
    setSaved(list.map((p) => ({ name: p.name, updated_at: p.updated_at })));
  }

  async function loadProject(name: string) {
    const p = await idb.loadProject(name);
    if (p) store.loadProject(p);
  }

  async function loadSampleDataset(filename: string) {
    const r = await fetch(`/samples/${filename}`);
    if (!r.ok) {
      alert(`Sample dataset not available at /samples/${filename}.`);
      return;
    }
    const blob = await r.blob();
    const file = new File([blob], filename, { type: "text/csv" });
    const payload = await api.importFile(file);
    store.set({ dataset: payload });
    store.logEvent("dataset_imported", { name: payload.name, n_rows: payload.rows.length });
  }

  return (
    <aside className={`${styles.sidebar} no-print`}>
      <section>
        <h3>Dataset</h3>
        {dataset ? (
          <div className={styles.dsBox}>
            <strong>{dataset.name}</strong>
            <small>{dataset.rows.length} filas &middot; {dataset.columns.length} cols</small>
          </div>
        ) : <p className={styles.empty}>Sin dataset.</p>}
      </section>

      <section>
        <h3>Columnas</h3>
        {dataset ? (
          <ul className={styles.cols}>
            {dataset.columns.map((c) => (
              <li key={c.name}>
                <span className={styles.colName}>{c.name}</span>
                <small className={styles.colType}>{c.type}</small>
              </li>
            ))}
          </ul>
        ) : <p className={styles.empty}>—</p>}
      </section>

      <section>
        <h3>Datasets de muestra</h3>
        <ul className={styles.samples}>
          {["iris.csv", "mtcars.csv", "ToothGrowth.csv", "AirPassengers.csv", "USArrests.csv", "spc_bottling.csv", "doe_factorial_2k.csv"].map((s) => (
            <li key={s}>
              <button onClick={() => loadSampleDataset(s)} data-testid={`sample-${s}`}>{s}</button>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h3>Proyectos (locales)</h3>
        {saved.length === 0 ? (
          <p className={styles.empty}>Sin proyectos guardados.</p>
        ) : (
          <ul className={styles.projects}>
            {saved.map((p) => (
              <li key={p.name}>
                <button onClick={() => loadProject(p.name)}>{p.name}</button>
                <small>{new Date(p.updated_at).toLocaleString()}</small>
              </li>
            ))}
          </ul>
        )}
        <button className={styles.refresh} onClick={refresh}>Actualizar</button>
      </section>

      <section>
        <h3>Resultados ({results.length})</h3>
        <ul className={styles.results}>
          {results.slice(-5).reverse().map((r) => (
            <li key={r.id}><small>{r.type}</small></li>
          ))}
        </ul>
      </section>

      <section>
        <h3>Historial</h3>
        <ul className={styles.history}>
          {history.slice(-10).reverse().map((e) => (
            <li key={e.id}>
              <code>{e.kind}</code>
              <small>{new Date(e.timestamp).toLocaleTimeString()}</small>
            </li>
          ))}
        </ul>
      </section>
    </aside>
  );
}
