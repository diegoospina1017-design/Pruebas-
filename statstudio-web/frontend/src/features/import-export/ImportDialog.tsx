import { useRef, useState } from "react";
import { api } from "@/lib/api";
import { store } from "@/lib/store";
import modal from "@/components/Modal.module.css";
import styles from "./ImportDialog.module.css";

export function ImportDialog({ onClose }: { onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<{ columns: any[]; rows: any[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const dropRef = useRef<HTMLDivElement>(null);

  async function pickFile(f: File) {
    setFile(f);
    setError(null);
    setPreview(null);
    setBusy(true);
    try {
      const p = await api.previewFile(f);
      setPreview(p);
    } catch (e: any) {
      setError(e.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  async function confirmImport() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const payload = await api.importFile(file);
      store.set({ dataset: payload });
      store.logEvent("dataset_imported", { name: payload.name, n_rows: payload.rows.length });
      onClose();
    } catch (e: any) {
      setError(e.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={modal.backdrop} onClick={onClose}>
      <div className={modal.modal} onClick={(e) => e.stopPropagation()} style={{ maxWidth: 800 }}>
        <header><h3>Importar datos</h3><button onClick={onClose}>×</button></header>
        <div className={modal.body}>
          <div
            ref={dropRef}
            className={styles.drop}
            onDragOver={(e) => { e.preventDefault(); dropRef.current?.classList.add(styles.dragOver); }}
            onDragLeave={() => dropRef.current?.classList.remove(styles.dragOver)}
            onDrop={(e) => {
              e.preventDefault();
              dropRef.current?.classList.remove(styles.dragOver);
              const f = e.dataTransfer.files?.[0];
              if (f) pickFile(f);
            }}
          >
            <p>Arrastra un archivo CSV / XLSX aquí, o</p>
            <label className={styles.fileBtn}>
              <span>Elegir archivo…</span>
              <input
                type="file"
                accept=".csv,.xlsx,.xls"
                onChange={(e) => e.target.files?.[0] && pickFile(e.target.files[0])}
                data-testid="file-input"
              />
            </label>
            {file && <small>{file.name} &middot; {(file.size / 1024).toFixed(1)} KB</small>}
          </div>
          {error && <div className={modal.error}>{error}</div>}
          {preview && (
            <div className={styles.preview}>
              <h4>Vista previa (primeras filas)</h4>
              <div className={styles.tableWrap}>
                <table>
                  <thead>
                    <tr>
                      {preview.columns.map((c: any) => (
                        <th key={c.name}>{c.name}<br /><small>{c.type}</small></th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.slice(0, 20).map((row: any, i: number) => (
                      <tr key={i}>
                        {preview.columns.map((c: any) => (
                          <td key={c.name}>{row[c.name] == null ? "" : String(row[c.name])}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
        <div className={modal.footer}>
          <button onClick={onClose}>Cancelar</button>
          <button className="primary" onClick={confirmImport} disabled={!file || busy} data-testid="confirm-import">
            {busy ? "Importando…" : "Importar"}
          </button>
        </div>
      </div>
    </div>
  );
}
