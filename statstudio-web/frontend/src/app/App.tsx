import { useEffect, useState } from "react";
import { Toolbar } from "@/components/Toolbar";
import { Sidebar } from "@/components/Sidebar";
import { DataGridView } from "@/features/data-grid/DataGridView";
import { ResultsPanel } from "@/features/results/ResultsPanel";
import { DashboardView } from "@/features/dashboards/DashboardView";
import { AnalysisDialogs, type DialogKey } from "@/features/analysis-dialogs/AnalysisDialogs";
import { ImportDialog } from "@/features/import-export/ImportDialog";
import { ShortcutsHelp } from "@/components/ShortcutsHelp";
import { store, useStore } from "@/lib/store";
import { idb } from "@/lib/idb";
import { api } from "@/lib/api";
import styles from "./App.module.css";

type Tab = "data" | "results" | "dashboard";

export function App() {
  const dataset = useStore((s) => s.dataset);
  const projectName = useStore((s) => s.projectName);
  const [tab, setTab] = useState<Tab>("data");
  const [dialog, setDialog] = useState<DialogKey | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  // keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return;
      const cmd = e.ctrlKey || e.metaKey;
      if (cmd && e.key.toLowerCase() === "o") { e.preventDefault(); setImportOpen(true); }
      else if (cmd && e.key.toLowerCase() === "s") { e.preventDefault(); saveProject(); }
      else if (cmd && e.key.toLowerCase() === "p") { e.preventDefault(); printReport(); }
      else if (e.key === "?") { setHelpOpen(true); }
      else if (e.key === "Escape") { setDialog(null); setImportOpen(false); setHelpOpen(false); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  async function saveProject() {
    const p = store.toProject();
    await idb.saveProject(p);
    const blob = await api.exportProjectJson(p);
    downloadBlob(blob, `${p.name}.statstudio.json`);
    store.logEvent("project_saved", { name: p.name });
  }

  async function printReport() {
    const html = await api.exportHtmlReport(projectName, store.get().results);
    const w = window.open("", "_blank");
    if (!w) return;
    w.document.write(html);
    w.document.close();
    setTimeout(() => w.print(), 800);
  }

  return (
    <div className={styles.app}>
      <Toolbar
        onImport={() => setImportOpen(true)}
        onSave={saveProject}
        onPrint={printReport}
        onOpenDialog={setDialog}
        onShowHelp={() => setHelpOpen(true)}
        tab={tab}
        onTabChange={setTab}
      />
      <div className={styles.body}>
        <Sidebar />
        <main className={styles.main} data-testid="main-area">
          {tab === "data" && (dataset
            ? <DataGridView />
            : <EmptyState onImport={() => setImportOpen(true)} />)}
          {tab === "results" && <ResultsPanel />}
          {tab === "dashboard" && <DashboardView />}
        </main>
      </div>
      {importOpen && <ImportDialog onClose={() => setImportOpen(false)} />}
      {dialog && <AnalysisDialogs which={dialog} onClose={() => setDialog(null)} />}
      {helpOpen && <ShortcutsHelp onClose={() => setHelpOpen(false)} />}
    </div>
  );
}

function EmptyState({ onImport }: { onImport: () => void }) {
  return (
    <div className={styles.empty}>
      <h2>Bienvenido a StatStudio Web</h2>
      <p>Una plataforma web de análisis estadístico al estilo Minitab/JMP.</p>
      <button className="primary" onClick={onImport} data-testid="empty-import-btn">
        Importar datos (CSV / Excel)
      </button>
      <p style={{ marginTop: 20, color: "var(--fg-muted)" }}>
        Atajos: <kbd>Ctrl/Cmd+O</kbd> importar &middot; <kbd>Ctrl/Cmd+S</kbd> guardar &middot; <kbd>?</kbd> ayuda
      </p>
    </div>
  );
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
