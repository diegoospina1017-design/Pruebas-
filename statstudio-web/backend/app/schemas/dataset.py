"""Dataset schemas."""
from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

ColumnType = Literal["numeric", "integer", "categorical", "boolean", "datetime", "text"]


class ColumnMeta(BaseModel):
    name: str
    type: ColumnType = "text"
    nullable: bool = True
    n_missing: int = 0
    unique_count: Optional[int] = None
    sample_values: list[Any] = Field(default_factory=list)


class DatasetMeta(BaseModel):
    id: str
    name: str
    n_rows: int
    n_cols: int
    columns: list[ColumnMeta]
    created_at: str


class DatasetPayload(BaseModel):
    """Inline dataset payload (used when frontend sends columnar data)."""
    name: str
    columns: list[ColumnMeta]
    rows: list[dict[str, Any]]
    row_ids: Optional[list[str]] = None


class DatasetCleanRequest(BaseModel):
    dataset: DatasetPayload
    drop_missing: bool = False
    impute_strategy: Optional[Literal["mean", "median", "mode"]] = None
    columns: Optional[list[str]] = None
    detect_outliers: bool = False
    outlier_method: Literal["iqr", "zscore"] = "iqr"


class DatasetCleanResult(BaseModel):
    dataset: DatasetPayload
    summary: dict[str, Any]
