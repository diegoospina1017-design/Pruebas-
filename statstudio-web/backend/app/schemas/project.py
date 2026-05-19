"""Project file schemas."""
from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.schemas.dataset import DatasetPayload, DatasetMeta
from app.schemas.analysis import AnalysisRequest, AnalysisResult


class DashboardItem(BaseModel):
    id: str
    kind: str  # "chart" | "table" | "analysis"
    ref_id: str
    x: int = 0
    y: int = 0
    w: int = 6
    h: int = 4
    title: Optional[str] = None


class DashboardSpec(BaseModel):
    id: str
    name: str
    items: list[DashboardItem] = Field(default_factory=list)


class SessionEvent(BaseModel):
    id: str
    kind: str
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ProjectFile(BaseModel):
    schema_version: str = "1.0.0"
    app_version: str = "0.1.0"
    name: str
    created_at: str
    datasets: list[DatasetPayload] = Field(default_factory=list)
    dataset_meta: list[DatasetMeta] = Field(default_factory=list)
    analyses: list[AnalysisRequest] = Field(default_factory=list)
    results: list[AnalysisResult] = Field(default_factory=list)
    dashboards: list[DashboardSpec] = Field(default_factory=list)
    history: list[SessionEvent] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)
