// Helpers to inspect dataset columns.
import type { ColumnMeta, ColumnType, DatasetPayload } from "./types";

export function isNumericType(t: ColumnType): boolean {
  return t === "numeric" || t === "integer";
}

export function numericColumns(ds: DatasetPayload): ColumnMeta[] {
  return ds.columns.filter((c) => isNumericType(c.type));
}

export function categoricalColumns(ds: DatasetPayload): ColumnMeta[] {
  return ds.columns.filter((c) => c.type === "categorical" || c.type === "boolean" || c.type === "text");
}

export function columnNames(ds: DatasetPayload): string[] {
  return ds.columns.map((c) => c.name);
}

export function inferTypeFromValues(values: any[]): ColumnType {
  let numericish = 0;
  let total = 0;
  const unique = new Set<string>();
  for (const v of values) {
    if (v === null || v === undefined || v === "") continue;
    total++;
    unique.add(String(v));
    const n = Number(v);
    if (!Number.isNaN(n)) numericish++;
  }
  if (total === 0) return "text";
  if (numericish / total > 0.95) {
    // Integer if all numeric values are integers
    const allInt = values
      .filter((v) => v !== null && v !== undefined && v !== "")
      .every((v) => Number.isInteger(Number(v)));
    return allInt ? "integer" : "numeric";
  }
  if (unique.size <= Math.max(20, total * 0.05)) return "categorical";
  return "text";
}
