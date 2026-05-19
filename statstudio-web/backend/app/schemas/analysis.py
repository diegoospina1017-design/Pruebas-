"""Analysis request/response schemas."""
from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

from app.schemas.dataset import DatasetPayload


AnalysisType = Literal[
    "descriptives",
    "ttest_one_sample",
    "ttest_two_sample",
    "ttest_paired",
    "chi_square",
    "proportion_test",
    "anova_one_way",
    "regression_ols",
    "regression_logistic",
    "timeseries_summary",
    "timeseries_forecast",
    "control_chart_imr",
    "control_chart_xbar_r",
    "doe_factorial_design",
    "doe_factorial_analyze",
    "pca",
    "kmeans",
    "hclust",
]


class AnalysisRequest(BaseModel):
    type: AnalysisType
    dataset: DatasetPayload
    params: dict[str, Any] = Field(default_factory=dict)
    selection: Optional[list[str]] = None  # rowIds
    options: dict[str, Any] = Field(default_factory=dict)


class TableSpec(BaseModel):
    id: str
    title: str
    columns: list[str]
    rows: list[list[Any]]
    notes: Optional[str] = None


class ChartSpec(BaseModel):
    """A chart description that the frontend renders via Plotly."""
    id: str
    title: str
    kind: Literal[
        "histogram", "boxplot", "scatter", "line", "bar", "qq", "residuals",
        "pareto", "control", "biplot", "scree", "heatmap", "interaction", "effects",
    ]
    data: list[dict[str, Any]]  # plotly traces
    layout: dict[str, Any] = Field(default_factory=dict)
    row_ids: Optional[list[str]] = None  # for linked brushing


class AnalysisResult(BaseModel):
    id: str
    type: AnalysisType
    metadata: dict[str, Any]
    statistical_tables: list[TableSpec]
    charts: list[ChartSpec]
    textual_summary: str
    warnings: list[str] = Field(default_factory=list)
    reproducibility: dict[str, Any]
