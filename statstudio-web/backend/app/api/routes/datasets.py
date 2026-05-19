"""Dataset operations: clean, summarize."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, HTTPException
import pandas as pd
import numpy as np

from app.schemas.dataset import DatasetPayload, DatasetCleanRequest, DatasetCleanResult
from app.services.datasets.cleaning import clean_dataset
from app.utils.dataframe import payload_to_df, df_to_payload, numeric_columns

router = APIRouter()


@router.post("/clean", response_model=DatasetCleanResult)
def clean(req: DatasetCleanRequest):
    try:
        return clean_dataset(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/summary")
def summary(payload: DatasetPayload) -> dict[str, Any]:
    df = payload_to_df(payload)
    out = {
        "n_rows": int(len(df)),
        "n_cols": int(df.shape[1]),
        "missing_by_column": {c: int(df[c].isna().sum()) for c in df.columns},
        "numeric_columns": numeric_columns(df),
        "column_types": {c: str(df[c].dtype) for c in df.columns},
    }
    return out


@router.post("/pivot")
def pivot(body: dict[str, Any]) -> dict[str, Any]:
    """Simple pivot table via pandas."""
    payload = DatasetPayload(**body["dataset"])
    df = payload_to_df(payload)
    index = body.get("index")
    columns = body.get("columns")
    values = body.get("values")
    aggfunc = body.get("aggfunc", "mean")
    if not values:
        raise HTTPException(status_code=400, detail="`values` is required for pivot.")
    try:
        pv = pd.pivot_table(df, index=index, columns=columns, values=values, aggfunc=aggfunc)
        if isinstance(pv, pd.DataFrame):
            pv = pv.reset_index()
            return {"columns": [str(c) for c in pv.columns], "rows": pv.values.tolist()}
        return {"columns": ["value"], "rows": [[float(pv)]]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Pivot failed: {e}")
