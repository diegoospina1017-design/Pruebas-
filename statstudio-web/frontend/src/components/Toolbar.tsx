import { useStore } from "@/lib/store";
import type { DialogKey } from "@/features/analysis-dialogs/AnalysisDialogs";
import styles from "./Toolbar.module.css";

interface Props {
  onImport: () => void;
  onSave: () => void;
  onPrint: () => void;
  onShowHelp: () => void;
  onOpenDialog: (k: DialogKey) => void;
  tab: "data" | "results" | "dashboard";
  onTabChange: (t: "data" | "results" | "dashboard") => void;
}

const ANALYSIS_MENU: { label: string; key: DialogKey }[] = [
  { label: "Descriptivos", key: "descriptives" },
  { label: "t (una muestra)", key: "ttest_one_sample" },
  { label: "t (dos muestras)", key: "ttest_two_sample" },
  { label: "t pareada", key: "ttest_paired" },
  { label: "Chi-cuadrado", key: "chi_square" },
  { label: "Proporciones", key: "proportion_test" },
  { label: "ANOVA un factor", key: "anova_one_way" },
  { label: "Regresión OLS", key: "regression_ols" },
  { label: "Regresión logística", key: "regression_logistic" },
  { label: "Serie de tiempo", key: "timeseries_summary" },
  { label: "Forecast", key: "timeseries_forecast" },
  { label: "Carta I-MR", key: "control_chart_imr" },
  { label: "Carta Xbar-R", key: "control_chart_xbar_r" },
  { label: "DOE: diseño 2^k", key: "doe_factorial_design" },
  { label: "DOE: analizar factorial", key: "doe_factorial_analyze" },
  { label: "PCA", key: "pca" },
  { label: "K-means", key: "kmeans" },
  { label: "Cluster jerárquico", key: "hclust" },
];

export function Toolbar({
  onImport, onSave, onPrint, onShowHelp, onOpenDialog, tab, onTabChange,
}: Props) {
  const projectName = useStore((s) => s.projectName);
  const hasDataset = useStore((s) => s.dataset != null);

  return (
    <header className={`${styles.toolbar} no-print`}>
      <div className={styles.brand}>
        <span className={styles.logo}>S</span>
        <strong>StatStudio Web</strong>
        <span className={styles.projectName}>{projectName}</span>
      </div>
      <div className={styles.actions}>
        <button onClick={onImport} data-testid="btn-import">Importar</button>
        <button onClick={onSave} data-testid="btn-save" disabled={!hasDataset}>Guardar</button>
        <button onClick={onPrint} disabled={!hasDataset}>Reporte</button>
        <details className={styles.menu}>
          <summary>Análisis ▾</summary>
          <div className={styles.menuItems}>
            {ANALYSIS_MENU.map((m) => (
              <button
                key={m.key}
                disabled={!hasDataset}
                onClick={(e) => { onOpenDialog(m.key); (e.currentTarget.closest("details") as HTMLDetailsElement)?.removeAttribute("open"); }}
                data-testid={`menu-${m.key}`}
              >
                {m.label}
              </button>
            ))}
          </div>
        </details>
        <div className={styles.tabs}>
          <button className={tab === "data" ? styles.tabActive : styles.tab} onClick={() => onTabChange("data")}>Datos</button>
          <button className={tab === "results" ? styles.tabActive : styles.tab} onClick={() => onTabChange("results")} data-testid="tab-results">Resultados</button>
          <button className={tab === "dashboard" ? styles.tabActive : styles.tab} onClick={() => onTabChange("dashboard")} data-testid="tab-dashboard">Dashboard</button>
        </div>
        <button onClick={onShowHelp} title="Atajos" className={styles.helpBtn}>?</button>
      </div>
    </header>
  );
}
