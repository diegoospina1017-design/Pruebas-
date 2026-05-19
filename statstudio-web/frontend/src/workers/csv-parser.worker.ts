/// <reference lib="webworker" />
// Worker for off-main-thread CSV parsing. Currently the backend handles import
// for any file > a few KB, but this worker is wired for quick client-side
// previews of small files so the UI stays responsive.

import { inferTypeFromValues } from "@/lib/columns";

self.onmessage = (e: MessageEvent<{ text: string; max?: number }>) => {
  const { text, max = 200 } = e.data;
  const lines = text.split(/\r?\n/).filter(Boolean);
  if (lines.length === 0) {
    (self as unknown as Worker).postMessage({ columns: [], rows: [] });
    return;
  }
  const header = parseLine(lines[0]);
  const rows: any[] = [];
  for (let i = 1; i < Math.min(lines.length, max + 1); i++) {
    const cells = parseLine(lines[i]);
    const r: Record<string, any> = {};
    header.forEach((h, j) => r[h] = cells[j] ?? null);
    rows.push(r);
  }
  const columns = header.map((h) => ({
    name: h,
    type: inferTypeFromValues(rows.map((r) => r[h])),
  }));
  (self as unknown as Worker).postMessage({ columns, rows });
};

function parseLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQuotes) {
      if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; }
      else if (ch === '"') inQuotes = false;
      else cur += ch;
    } else {
      if (ch === '"') inQuotes = true;
      else if (ch === ',') { out.push(cur); cur = ""; }
      else cur += ch;
    }
  }
  out.push(cur);
  return out;
}
