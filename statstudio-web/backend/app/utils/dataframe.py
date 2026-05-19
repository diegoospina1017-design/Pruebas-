"""Helpers to convert DatasetPayload <-> pandas DataFrame."""
from __future__ import annotations
from typing import Any
import pandas as pd
import numpy as np

from app.schemas.dataset import DatasetPayload, ColumnMeta


_PANDAS_DTYPE_MAP = {
    "numeric": "float64",
    "integer": "Int64",
    "boolean": "boolean",
    "categorical": "category",
    "datetime": "datetime64[ns]",
    "text": "string",
}


def payload_to_df(payload: DatasetPayload) -> pd.DataFrame:
    """Convert a DatasetPayload to a typed pandas DataFrame.

    The frontend always sends row-oriented JSON. We rebuild a DataFrame
    column-by-column to apply types correctly.
    """
    if not payload.rows:
        return pd.DataFrame({c.name: [] for c in payload.columns})

    df = pd.DataFrame(payload.rows)
    # ensure column order from columns metadata
    cols = [c.name for c in payload.columns if c.name in df.columns]
    df = df[cols]

    for c in payload.columns:
        if c.name not in df.columns:
            continue
        target = _PANDAS_DTYPE_MAP.get(c.type, "string")
        try:
            if c.type == "numeric":
                df[c.name] = pd.to_numeric(df[c.name], errors="coerce")
            elif c.type == "integer":
                df[c.name] = pd.to_numeric(df[c.name], errors="coerce").astype("Int64")
            elif c.type == "boolean":
                df[c.name] = df[c.name].map(_to_bool).astype("boolean")
            elif c.type == "datetime":
                df[c.name] = pd.to_datetime(df[c.name], errors="coerce")
            elif c.type == "categorical":
                df[c.name] = df[c.name].astype("string").astype("category")
            else:
                df[c.name] = df[c.name].astype("string")
        except Exception:
            try:
                df[c.name] = df[c.name].astype(target)
            except Exception:
                pass

    if payload.row_ids and len(payload.row_ids) == len(df):
        df.index = pd.Index(payload.row_ids, name="row_id")
    else:
        df.index = pd.Index([f"r{i}" for i in range(len(df))], name="row_id")
    return df


def _to_bool(v: Any) -> Any:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return pd.NA
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).strip().lower()
    if s in ("true", "t", "yes", "y", "1"):
        return True
    if s in ("false", "f", "no", "n", "0"):
        return False
    return pd.NA


def df_to_payload(df: pd.DataFrame, name: str) -> DatasetPayload:
    """Reverse: pandas DataFrame -> DatasetPayload."""
    columns: list[ColumnMeta] = []
    for col in df.columns:
        s = df[col]
        ctype = _infer_type(s)
        columns.append(
            ColumnMeta(
                name=str(col),
                type=ctype,
                nullable=True,
                n_missing=int(s.isna().sum()),
                unique_count=int(s.nunique(dropna=True)),
                sample_values=[_jsonable(v) for v in s.dropna().head(5).tolist()],
            )
        )
    row_ids = [str(i) for i in df.index.tolist()]
    rows = []
    for _, r in df.iterrows():
        rows.append({str(k): _jsonable(v) for k, v in r.items()})
    return DatasetPayload(name=name, columns=columns, rows=rows, row_ids=row_ids)


def _infer_type(s: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(s):
        return "boolean"
    if pd.api.types.is_integer_dtype(s):
        return "integer"
    if pd.api.types.is_float_dtype(s):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "datetime"
    if isinstance(s.dtype, pd.CategoricalDtype):
        return "categorical"
    # heuristic: low-cardinality strings -> categorical
    nu = s.nunique(dropna=True)
    if 0 < nu <= max(20, int(0.05 * len(s))) and pd.api.types.is_string_dtype(s):
        return "categorical"
    return "text"


def _jsonable(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (bool, int, float, str)):
        if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
            return None
        return v
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        x = float(v)
        return None if (np.isnan(x) or np.isinf(x)) else x
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    if pd.isna(v):
        return None
    return str(v)


def numeric_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]


def categorical_columns(df: pd.DataFrame) -> list[str]:
    return [
        c for c in df.columns
        if not pd.api.types.is_numeric_dtype(df[c])
        and not pd.api.types.is_datetime64_any_dtype(df[c])
    ]
