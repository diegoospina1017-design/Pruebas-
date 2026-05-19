import { useEffect, useRef } from "react";
import Plotly from "plotly.js-dist-min";
import type { ChartSpec } from "@/lib/types";
import { store, useStore } from "@/lib/store";

interface Props {
  spec: ChartSpec;
  height?: number;
}

export function PlotlyChart({ spec, height = 320 }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const selection = useStore((s) => s.selection);

  useEffect(() => {
    if (!ref.current) return;
    const layout = {
      autosize: true,
      margin: { t: 36, l: 50, r: 20, b: 40 },
      title: { text: spec.title, font: { size: 14 } },
      ...spec.layout,
    };
    const data = applyBrushing(spec, selection);
    Plotly.react(ref.current, data, layout, { responsive: true, displaylogo: false });

    // Linked brushing: click points to toggle selection
    const handler = (event: any) => {
      const ids = (event.points || [])
        .map((p: any) => (p.customdata as string) ?? p.id)
        .filter(Boolean);
      if (!ids.length) return;
      const next = new Set(store.get().selection);
      ids.forEach((id: string) => next.has(id) ? next.delete(id) : next.add(id));
      store.setSelection(next);
    };
    const selHandler = (event: any) => {
      const ids = (event?.points || [])
        .map((p: any) => p.customdata)
        .filter(Boolean);
      if (ids.length) store.setSelection(ids);
    };
    (ref.current as any).on?.("plotly_click", handler);
    (ref.current as any).on?.("plotly_selected", selHandler);
    return () => {
      try { Plotly.purge(ref.current!); } catch { /* noop */ }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spec, selection]);

  return <div ref={ref} style={{ width: "100%", height }} data-testid={`plotly-${spec.kind}`} />;
}

function applyBrushing(spec: ChartSpec, selection: Set<string>): any[] {
  if (selection.size === 0) return spec.data;
  return spec.data.map((trace) => {
    if (!trace || !trace.customdata) return trace;
    const sizes = trace.customdata.map((id: string) => (selection.has(id) ? 11 : 6));
    const colors = trace.customdata.map((id: string) =>
      selection.has(id) ? "#dc2626" : (trace.marker?.color ?? "#2563eb"),
    );
    return {
      ...trace,
      marker: {
        ...(trace.marker ?? {}),
        size: sizes,
        color: colors,
        line: { width: trace.customdata.map((id: string) => (selection.has(id) ? 2 : 0)), color: "white" },
      },
    };
  });
}
