"""Control charts: I-MR and Xbar-R."""
from __future__ import annotations
import uuid
import numpy as np
import pandas as pd

from app.schemas.analysis import AnalysisRequest, AnalysisResult, TableSpec, ChartSpec
from app.utils.dataframe import payload_to_df
from app.services.analysis._common import make_result, fmt, line_trace, scatter_trace, require_columns


# Constants for Shewhart control charts (Montgomery, table)
_D3 = {2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.076, 8: 0.136, 9: 0.184, 10: 0.223}
_D4 = {2: 3.267, 3: 2.575, 4: 2.282, 5: 2.115, 6: 2.004, 7: 1.924, 8: 1.864, 9: 1.816, 10: 1.777}
_A2 = {2: 1.880, 3: 1.023, 4: 0.729, 5: 0.577, 6: 0.483, 7: 0.419, 8: 0.373, 9: 0.337, 10: 0.308}
_D2 = {2: 1.128, 3: 1.693, 4: 2.059, 5: 2.326, 6: 2.534, 7: 2.704, 8: 2.847, 9: 2.970, 10: 3.078}


def run_imr_chart(req: AnalysisRequest) -> AnalysisResult:
    df = payload_to_df(req.dataset)
    col = req.params["column"]
    phase_col = req.params.get("phase_column")
    require_columns(df, [col])
    s = pd.to_numeric(df[col], errors="coerce")
    valid = s.dropna()
    if len(valid) < 2:
        raise ValueError("Need at least 2 observations for I-MR.")

    mr = valid.diff().abs().dropna()
    mr_bar = mr.mean()
    x_bar = valid.mean()
    # I chart constants for n=2 moving range
    d2 = _D2[2]
    sigma = mr_bar / d2
    ucl_i = x_bar + 3 * sigma
    lcl_i = x_bar - 3 * sigma
    ucl_mr = _D4[2] * mr_bar
    lcl_mr = _D3[2] * mr_bar

    x_idx = list(range(1, len(valid) + 1))
    flags_i = [bool((v > ucl_i) or (v < lcl_i)) for v in valid.values]
    flags_mr = [bool((v > ucl_mr) or (v < lcl_mr)) for v in mr.values]

    chart_i = ChartSpec(
        id=str(uuid.uuid4()), title=f"I chart - {col}", kind="control",
        data=[
            line_trace(x_idx, valid.values, name="x"),
            line_trace(x_idx, [x_bar] * len(x_idx), name="CL"),
            line_trace(x_idx, [ucl_i] * len(x_idx), name="UCL"),
            line_trace(x_idx, [lcl_i] * len(x_idx), name="LCL"),
            scatter_trace(
                [x_idx[i] for i, f in enumerate(flags_i) if f],
                [valid.values[i] for i, f in enumerate(flags_i) if f],
                name="out-of-control",
            ),
        ],
        layout={"xaxis": {"title": "obs"}, "yaxis": {"title": col}},
    )
    chart_mr = ChartSpec(
        id=str(uuid.uuid4()), title="Moving Range chart", kind="control",
        data=[
            line_trace(x_idx[1:], mr.values, name="MR"),
            line_trace(x_idx[1:], [mr_bar] * len(mr), name="CL"),
            line_trace(x_idx[1:], [ucl_mr] * len(mr), name="UCL"),
            line_trace(x_idx[1:], [lcl_mr] * len(mr), name="LCL"),
        ],
        layout={"xaxis": {"title": "obs"}, "yaxis": {"title": "MR"}},
    )

    table = TableSpec(
        id=str(uuid.uuid4()), title="I-MR control limits",
        columns=["mean", "MR_bar", "sigma", "UCL_I", "LCL_I", "UCL_MR", "LCL_MR", "n_signals_I", "n_signals_MR"],
        rows=[[fmt(x_bar), fmt(mr_bar), fmt(sigma), fmt(ucl_i), fmt(lcl_i),
               fmt(ucl_mr), fmt(lcl_mr), int(sum(flags_i)), int(sum(flags_mr))]],
    )
    return make_result(
        req, [table], [chart_i, chart_mr],
        f"I-MR chart for '{col}': {sum(flags_i)} individual signal(s), {sum(flags_mr)} MR signal(s).",
    )


def run_xbar_r_chart(req: AnalysisRequest) -> AnalysisResult:
    df = payload_to_df(req.dataset)
    col = req.params["column"]
    subgroup_col = req.params["subgroup_column"]
    require_columns(df, [col, subgroup_col])

    grouped = df.groupby(subgroup_col, sort=True)[col].apply(lambda x: pd.to_numeric(x, errors="coerce").dropna())
    subs = [g for _, g in grouped.groupby(level=0)]
    sizes = [len(g) for g in subs]
    if not sizes:
        raise ValueError("No valid subgroups.")
    n = sizes[0]
    if any(sz != n for sz in sizes):
        raise ValueError(f"Subgroups must have equal size; got {sizes}.")
    if n < 2 or n > 10:
        raise ValueError("Subgroup size must be in 2..10.")

    means = np.array([g.mean() for g in subs])
    ranges = np.array([g.max() - g.min() for g in subs])
    xbar_bar = means.mean()
    rbar = ranges.mean()
    ucl_x = xbar_bar + _A2[n] * rbar
    lcl_x = xbar_bar - _A2[n] * rbar
    ucl_r = _D4[n] * rbar
    lcl_r = _D3[n] * rbar

    labels = list(grouped.groupby(level=0).groups.keys())
    flags_x = [bool((v > ucl_x) or (v < lcl_x)) for v in means]
    flags_r = [bool((v > ucl_r) or (v < lcl_r)) for v in ranges]

    chart_x = ChartSpec(
        id=str(uuid.uuid4()), title=f"Xbar chart - {col} (n={n})", kind="control",
        data=[
            line_trace([str(l) for l in labels], means.tolist(), name="xbar"),
            line_trace([str(l) for l in labels], [xbar_bar] * len(means), name="CL"),
            line_trace([str(l) for l in labels], [ucl_x] * len(means), name="UCL"),
            line_trace([str(l) for l in labels], [lcl_x] * len(means), name="LCL"),
        ],
        layout={"xaxis": {"title": subgroup_col}, "yaxis": {"title": f"xbar({col})"}},
    )
    chart_r = ChartSpec(
        id=str(uuid.uuid4()), title=f"R chart - {col}", kind="control",
        data=[
            line_trace([str(l) for l in labels], ranges.tolist(), name="R"),
            line_trace([str(l) for l in labels], [rbar] * len(ranges), name="CL"),
            line_trace([str(l) for l in labels], [ucl_r] * len(ranges), name="UCL"),
            line_trace([str(l) for l in labels], [lcl_r] * len(ranges), name="LCL"),
        ],
        layout={"xaxis": {"title": subgroup_col}, "yaxis": {"title": "R"}},
    )
    table = TableSpec(
        id=str(uuid.uuid4()), title="Xbar-R control limits",
        columns=["xbar_bar", "R_bar", "UCL_X", "LCL_X", "UCL_R", "LCL_R", "n_signals_X", "n_signals_R", "subgroup_n"],
        rows=[[fmt(xbar_bar), fmt(rbar), fmt(ucl_x), fmt(lcl_x), fmt(ucl_r), fmt(lcl_r),
               int(sum(flags_x)), int(sum(flags_r)), n]],
    )
    return make_result(
        req, [table], [chart_x, chart_r],
        f"Xbar-R chart: {sum(flags_x)} xbar signal(s), {sum(flags_r)} R signal(s).",
    )
