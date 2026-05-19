"""Dataset import/export utilities."""
from __future__ import annotations
from io import BytesIO, StringIO
import pandas as pd

from app.schemas.dataset import DatasetPayload
from app.utils.dataframe import df_to_payload, payload_to_df


def import_csv(content: bytes, name: str = "dataset") -> DatasetPayload:
    text = content.decode("utf-8-sig", errors="replace")
    df = pd.read_csv(StringIO(text))
    return df_to_payload(df, name=name)


def import_excel(content: bytes, name: str = "dataset", sheet: str | int = 0) -> DatasetPayload:
    df = pd.read_excel(BytesIO(content), sheet_name=sheet)
    if isinstance(df, dict):
        df = next(iter(df.values()))
    return df_to_payload(df, name=name)


def export_csv(payload: DatasetPayload) -> bytes:
    df = payload_to_df(payload)
    buf = StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def export_excel(payload: DatasetPayload) -> bytes:
    df = payload_to_df(payload)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="data")
    return buf.getvalue()


def preview_csv(content: bytes, n: int = 50) -> dict:
    text = content.decode("utf-8-sig", errors="replace")
    df = pd.read_csv(StringIO(text), nrows=n)
    payload = df_to_payload(df, name="preview")
    return {
        "columns": [c.model_dump() for c in payload.columns],
        "rows": payload.rows,
        "row_ids": payload.row_ids,
    }
