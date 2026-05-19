"""Render an HTML report from a list of AnalysisResult objects."""
from __future__ import annotations
from html import escape
import json
from datetime import datetime

from app.schemas.analysis import AnalysisResult


def render_html_report(results: list[AnalysisResult], title: str = "StatStudio Report") -> str:
    parts: list[str] = []
    parts.append("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">")
    parts.append(f"<title>{escape(title)}</title>")
    parts.append(
        "<script src=\"https://cdn.plot.ly/plotly-2.30.0.min.js\"></script>"
        "<style>body{font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#1f2933;}"
        "h1{border-bottom:1px solid #ddd;padding-bottom:.4em;}"
        "h2{margin-top:2em;color:#243b53;}"
        "table{border-collapse:collapse;width:100%;margin:1em 0;font-size:14px;}"
        "th,td{border:1px solid #d8dee5;padding:6px 8px;text-align:left;}"
        "th{background:#f0f4f8;}"
        ".chart{margin:1em 0;}"
        ".summary{background:#f0f4f8;padding:10px 14px;border-left:4px solid #486581;}"
        "@media print { .chart{break-inside:avoid;} }"
        "</style></head><body>"
    )
    parts.append(f"<h1>{escape(title)}</h1>")
    parts.append(f"<p><em>Generated {datetime.utcnow().isoformat()}Z &middot; {len(results)} analysis(es)</em></p>")

    for i, r in enumerate(results, start=1):
        parts.append(f"<h2>{i}. {escape(r.type)} &mdash; <small>{escape(r.id[:8])}</small></h2>")
        parts.append(f"<div class=\"summary\">{escape(r.textual_summary or '')}</div>")
        for t in r.statistical_tables:
            parts.append(f"<h3>{escape(t.title)}</h3>")
            parts.append("<table><thead><tr>")
            parts.append("".join(f"<th>{escape(str(c))}</th>" for c in t.columns))
            parts.append("</tr></thead><tbody>")
            for row in t.rows:
                parts.append("<tr>" + "".join(f"<td>{escape(str(c)) if c is not None else ''}</td>" for c in row) + "</tr>")
            parts.append("</tbody></table>")
        for ci, ch in enumerate(r.charts):
            chart_id = f"chart_{i}_{ci}"
            parts.append(f"<div class=\"chart\"><h4>{escape(ch.title)}</h4><div id=\"{chart_id}\" style=\"height:380px;\"></div>")
            parts.append(
                f"<script>Plotly.newPlot('{chart_id}', {json.dumps(ch.data)}, "
                f"Object.assign({{title: {json.dumps(ch.title)}}}, {json.dumps(ch.layout)}), {{responsive:true}});</script></div>"
            )
        if r.warnings:
            parts.append("<details><summary>Warnings</summary><ul>")
            for w in r.warnings:
                parts.append(f"<li>{escape(w)}</li>")
            parts.append("</ul></details>")
    parts.append("</body></html>")
    return "".join(parts)
