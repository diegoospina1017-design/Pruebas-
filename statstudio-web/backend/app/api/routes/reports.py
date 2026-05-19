from __future__ import annotations
from typing import Any
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from app.schemas.analysis import AnalysisResult
from app.services.reporting.html_report import render_html_report

router = APIRouter()


@router.post("/export/html", response_class=HTMLResponse)
def export_html(payload: dict[str, Any]):
    title = payload.get("title", "StatStudio Report")
    raw_results = payload.get("results", [])
    results = [AnalysisResult(**r) for r in raw_results]
    html = render_html_report(results, title=title)
    return Response(
        content=html, media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{title}.html"'},
    )
