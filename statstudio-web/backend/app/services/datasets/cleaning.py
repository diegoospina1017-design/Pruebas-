"""Dataset cleaning: missing imputation, outlier detection."""
from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd

from app.schemas.dataset import DatasetCleanRequest, DatasetCleanResult
from app.utils.dataframe import payload_to_df, df_to_payload


def clean_dataset(req: DatasetCleanRequest) -> DatasetCleanResult:
    df = payload_to_df(req.dataset)
    cols = req.columns or list(df.columns)
    summary: dict[str, Any] = {"missing_before": {}, "missing_after": {}, "outliers": {}}

    for c in cols:
        if c not in df.columns:
            continue
        summary["missing_before"][c] = int(df[c].isna().sum())

    if req.drop_missing:
        df = df.dropna(subset=cols)
    elif req.impute_strategy:
        for c in cols:
            if c not in df.columns:
                continue
            if pd.api.types.is_numeric_dtype(df[c]):
                if req.impute_strategy == "mean":
                    df[c] = df[c].fillna(df[c].mean())
                elif req.impute_strategy == "median":
                    df[c] = df[c].fillna(df[c].median())
                elif req.impute_strategy == "mode":
                    if not df[c].dropna().empty:
                        df[c] = df[c].fillna(df[c].mode().iloc[0])
            else:
                if not df[c].dropna().empty:
                    df[c] = df[c].fillna(df[c].mode().iloc[0])

    if req.detect_outliers:
        for c in cols:
            if c not in df.columns or not pd.api.types.is_numeric_dtype(df[c]):
                continue
            s = pd.to_numeric(df[c], errors="coerce")
            if req.outlier_method == "iqr":
                q1, q3 = np.nanpercentile(s, [25, 75])
                iqr = q3 - q1
                lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            else:
                mu, sd = np.nanmean(s), np.nanstd(s)
                lo, hi = mu - 3 * sd, mu + 3 * sd
            mask = (s < lo) | (s > hi)
            summary["outliers"][c] = {
                "method": req.outlier_method,
                "lower": float(lo) if np.isfinite(lo) else None,
                "upper": float(hi) if np.isfinite(hi) else None,
                "count": int(mask.sum()),
                "row_ids": [str(i) for i in s.index[mask.fillna(False)]],
            }

    for c in cols:
        if c in df.columns:
            summary["missing_after"][c] = int(df[c].isna().sum())

    return DatasetCleanResult(
        dataset=df_to_payload(df, req.dataset.name),
        summary=summary,
    )
