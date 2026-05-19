import { useMemo, useRef, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import type { ColDef, GridApi, GridReadyEvent, SelectionChangedEvent } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";

import { store, useStore } from "@/lib/store";
import type { ColumnType } from "@/lib/types";
import { api } from "@/lib/api";
import styles from "./DataGridView.module.css";

const TYPE_OPTIONS: ColumnType[] = ["numeric", "integer", "categorical", "boolean", "datetime", "text"];

export function DataGridView() {
  const dataset = useStore((s) => s.dataset)!;
  const selection = useStore((s) => s.selection);
  const apiRef = useRef<GridApi | null>(null);
  const [filter, setFilter] = useState("");

  const columnDefs = useMemo<ColDef[]>(() => {
    return [
      { headerName: "#", valueGetter: "node.rowIndex+1", maxWidth: 56, pinned: "left", filter: false, sortable: false, editable: false },
      ...dataset.columns.map((c) => {
        const isNum = c.type === "numeric" || c.type === "integer";
        return {
          field: c.name,
          headerName: `${c.name} (${c.type})`,
          editable: true,
          filter: isNum ? "agNumberColumnFilter" : "agTextColumnFilter",
          sortable: true,
          resizable: true,
          valueParser: isNum
            ? (p: any) => (p.newValue === "" || p.newValue == null ? null : Number(p.newValue))
            : undefined,
        } as ColDef;
      }),
    ];
  }, [dataset]);

  const rowData = useMemo(() => {
    const ids = dataset.row_ids ?? dataset.rows.map((_, i) => String(i));
    return dataset.rows.map((r, i) => ({ __id: ids[i], ...r }));
  }, [dataset]);

  const onSelectionChanged = (e: SelectionChangedEvent) => {
    const ids = e.api.getSelectedNodes().map((n) => (n.data as any).__id as string);
    store.setSelection(ids);
  };

  const onGridReady = (e: GridReadyEvent) => {
    apiRef.current = e.api;
  };

  function onCellValueChanged(e: any) {
    const newRows = dataset.rows.map((r, i) => (i === e.rowIndex ? { ...r, [e.colDef.field]: e.newValue } : r));
    store.set({ dataset: { ...dataset, rows: newRows } });
    store.logEvent("cell_edit", { row: e.rowIndex, col: e.colDef.field });
  }

  function changeColumnType(name: string, type: ColumnType) {
    const cols = dataset.columns.map((c) => (c.name === name ? { ...c, type } : c));
    store.set({ dataset: { ...dataset, columns: cols } });
    store.logEvent("column_type_change", { column: name, type });
  }

  function renameColumn(oldName: string) {
    const newName = prompt(`Renombrar columna "${oldName}" a:`, oldName);
    if (!newName || newName === oldName) return;
    if (dataset.columns.some((c) => c.name === newName)) {
      alert("Ya existe una columna con ese nombre.");
      return;
    }
    const cols = dataset.columns.map((c) => (c.name === oldName ? { ...c, name: newName } : c));
    const rows = dataset.rows.map((r) => {
      const { [oldName]: v, ...rest } = r;
      return { ...rest, [newName]: v };
    });
    store.set({ dataset: { ...dataset, columns: cols, rows } });
    store.logEvent("column_rename", { from: oldName, to: newName });
  }

  function addCalculatedColumn() {
    const name = prompt("Nombre de la nueva columna calculada:");
    if (!name) return;
    if (dataset.columns.some((c) => c.name === name)) {
      alert("Ya existe.");
      return;
    }
    const formula = prompt(
      "Expresión usando ${columna}. Operadores: + - * / ( ). Ejemplo: ${mpg} * 1.609",
      "${mpg} * 1.609",
    );
    if (!formula) return;
    try {
      const rows = dataset.rows.map((r) => {
        const expr = formula.replace(/\$\{([^}]+)\}/g, (_, n) => {
          const v = Number(r[n]);
          return Number.isFinite(v) ? String(v) : "NaN";
        });
        // Sanitize: only digits, operators, whitespace, dot, parens, e for exponents
        if (!/^[\d+\-*/().\s eE]+$/.test(expr)) throw new Error("Expresión no permitida.");
        const fn = new Function(`"use strict"; return (${expr});`);
        const val = fn();
        return { ...r, [name]: Number.isFinite(val) ? val : null };
      });
      const newCol = { name, type: "numeric" as ColumnType, n_missing: 0 };
      store.set({ dataset: { ...dataset, columns: [...dataset.columns, newCol], rows } });
      store.logEvent("column_calculated", { name, formula });
    } catch (e: any) {
      alert(`Error en la fórmula: ${e.message ?? e}`);
    }
  }

  async function exportCsv() {
    const blob = await api.exportCsv(dataset);
    downloadBlob(blob, `${dataset.name}.csv`);
  }
  async function exportXlsx() {
    const blob = await api.exportXlsx(dataset);
    downloadBlob(blob, `${dataset.name}.xlsx`);
  }

  return (
    <div className={styles.container}>
      <div className={styles.controls}>
        <input
          placeholder="Buscar en grid…"
          value={filter}
          onChange={(e) => { setFilter(e.target.value); apiRef.current?.setGridOption("quickFilterText", e.target.value); }}
        />
        <button onClick={addCalculatedColumn}>+ Columna calculada</button>
        <button onClick={exportCsv}>Exportar CSV</button>
        <button onClick={exportXlsx}>Exportar XLSX</button>
        <span className={styles.spacer} />
        <small>Selección: {selection.size} fila(s)</small>
      </div>

      <div className={styles.typeBar}>
        {dataset.columns.map((c) => (
          <div key={c.name} className={styles.typePill}>
            <button onClick={() => renameColumn(c.name)} title="Renombrar">{c.name}</button>
            <select value={c.type} onChange={(e) => changeColumnType(c.name, e.target.value as ColumnType)}>
              {TYPE_OPTIONS.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        ))}
      </div>

      <div className={`${styles.grid} ag-theme-quartz`} data-testid="data-grid">
        <AgGridReact
          rowData={rowData}
          columnDefs={columnDefs}
          rowSelection="multiple"
          suppressRowClickSelection={false}
          onGridReady={onGridReady}
          onSelectionChanged={onSelectionChanged}
          onCellValueChanged={onCellValueChanged}
          stopEditingWhenCellsLoseFocus
          enableCellTextSelection
          undoRedoCellEditing
          undoRedoCellEditingLimit={50}
          getRowId={(p) => (p.data as any).__id}
        />
      </div>
    </div>
  );
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}
