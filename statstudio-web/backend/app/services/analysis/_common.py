"""Shared helpers for analysis services."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import uuid
import numpy as np
import pandas as pd

from app.schemas.analysis import AnalysisRequest, AnalysisResult, TableSpec, ChartSpec
from app import __version__


def _sanitize(obj):
    """Recursively convert numpy types to native python so pydantic can serialize."""
    if obj is None:
        return None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        x = float(obj)
        return None if (np.isnan(x) or np.isinf(x)) else x
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, (np.ndarray,)):
        return [_sanitize(x) for x in obj.tolist()]
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(x) for x in obj]
    if isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
    return obj


def make_result(
    req: AnalysisRequest,
    tables: list[TableSpec],
    charts: list[ChartSpec],
    summary: str,
    warnings: list[str] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> AnalysisResult:
    # Sanitize tables/charts so pydantic can serialize without numpy types
    clean_tables = [
        TableSpec(
            id=t.id, title=t.title, columns=t.columns,
            rows=[_sanitize(row) for row in t.rows],
            notes=t.notes,
        )
        for t in tables
    ]
    clean_charts = [
        ChartSpec(
            id=c.id, title=c.title, kind=c.kind,
            data=_sanitize(c.data),
            layout=_sanitize(c.layout),
            row_ids=c.row_ids,
        )
        for c in charts
    ]
    return AnalysisResult(
        id=str(uuid.uuid4()),
        type=req.type,
        metadata=_sanitize({
            "params": req.params,
            "options": req.options,
            "dataset_name": req.dataset.name,
            "n_rows": len(req.dataset.rows),
            "n_cols": len(req.dataset.columns),
            **(extra_metadata or {}),
        }),
        statistical_tables=clean_tables,
        charts=clean_charts,
        textual_summary=summary,
        warnings=warnings or [],
        reproducibility=_sanitize({
            "app_version": __version__,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "analysis_type": req.type,
            "params": req.params,
            "options": req.options,
        }),
    )


def fmt(v: Any, digits: int = 4) -> Any:
    if v is None:
        return None
    if isinstance(v, (np.floating, float)):
        if np.isnan(v) or np.isinf(v):
            return None
        return round(float(v), digits)
    if isinstance(v, (np.integer, int)):
        return int(v)
    return v


def safe_series(s: pd.Series) -> pd.Series:
    """Drop NaN/inf and return a numeric series."""
    s = pd.to_numeric(s, errors="coerce")
    return s.replace([np.inf, -np.inf], np.nan).dropna()


def require_columns(df: pd.DataFrame, names: list[str]) -> None:
    missing = [n for n in names if n not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in dataset: {missing}")


def histogram_trace(values: np.ndarray, name: str = "values") -> dict:
    return {"type": "histogram", "x": values.tolist(), "name": name, "opacity": 0.85}


def scatter_trace(x, y, name: str = "", row_ids: list[str] | None = None) -> dict:
    t: dict[str, Any] = {
        "type": "scatter", "mode": "markers", "x": list(x), "y": list(y), "name": name,
    }
    if row_ids:
        t["customdata"] = row_ids
        t["hovertemplate"] = "x=%{x}<br>y=%{y}<br>id=%{customdata}<extra></extra>"
    return t


def line_trace(x, y, name: str = "") -> dict:
    return {"type": "scatter", "mode": "lines", "x": list(x), "y": list(y), "name": name}


def box_trace(values, name: str = "") -> dict:
    return {"type": "box", "y": list(values), "name": name, "boxpoints": "outliers"}
