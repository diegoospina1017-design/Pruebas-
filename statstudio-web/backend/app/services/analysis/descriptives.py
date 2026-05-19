"""Descriptive statistics."""
from __future__ import annotations
import uuid
import numpy as np
import pandas as pd

from app.schemas.analysis import AnalysisRequest, AnalysisResult, TableSpec, ChartSpec
from app.utils.dataframe import payload_to_df, numeric_columns
from app.services.analysis._common import (
    make_result, fmt, histogram_trace, box_trace,
)


def run_descriptives(req: AnalysisRequest) -> AnalysisResult:
    df = payload_to_df(req.dataset)
    cols = req.params.get("columns") or numeric_columns(df)
    group_by = req.params.get("group_by")

    if not cols:
        return make_result(
            req,
            [],
            [],
            "No numeric columns available for descriptive statistics.",
            warnings=["No numeric columns detected."],
        )

    rows = []
    if group_by and group_by in df.columns:
        for col in cols:
            for level, sub in df.groupby(group_by, dropna=False):
                s = pd.to_numeric(sub[col], errors="coerce").dropna()
                if s.empty:
                    continue
                rows.append([col, str(level), *_stats(s)])
        table_cols = ["variable", "group", "n", "missing", "mean", "std", "min", "Q1", "median", "Q3", "max"]
    else:
        for col in cols:
            s = pd.to_numeric(df[col], errors="coerce").dropna()
            rows.append([col, *_stats(s)])
        table_cols = ["variable", "n", "missing", "mean", "std", "min", "Q1", "median", "Q3", "max"]

    table = TableSpec(
        id=str(uuid.uuid4()),
        title="Descriptive statistics",
        columns=table_cols,
        rows=rows,
    )

    charts: list[ChartSpec] = []
    for col in cols[:6]:  # cap to keep payload manageable
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            continue
        charts.append(
            ChartSpec(
                id=str(uuid.uuid4()),
                title=f"Histogram - {col}",
                kind="histogram",
                data=[histogram_trace(s.values, name=col)],
                layout={"xaxis": {"title": col}, "yaxis": {"title": "count"}, "bargap": 0.05},
            )
        )
        charts.append(
            ChartSpec(
                id=str(uuid.uuid4()),
                title=f"Boxplot - {col}",
                kind="boxplot",
                data=[box_trace(s.values, name=col)],
                layout={"yaxis": {"title": col}},
            )
        )

    summary = (
        f"Descriptive statistics for {len(cols)} variable(s)"
        + (f", grouped by '{group_by}'." if group_by else ".")
    )
    return make_result(req, [table], charts, summary)


def _stats(s: pd.Series) -> list:
    if s.empty:
        return [0, 0, None, None, None, None, None, None, None]
    return [
        int(s.shape[0]),
        int(s.isna().sum()),
        fmt(s.mean()),
        fmt(s.std(ddof=1)) if s.shape[0] > 1 else 0.0,
        fmt(s.min()),
        fmt(np.percentile(s, 25)),
        fmt(s.median()),
        fmt(np.percentile(s, 75)),
        fmt(s.max()),
    ]
