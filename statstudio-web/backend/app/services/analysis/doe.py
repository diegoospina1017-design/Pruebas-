"""Design of Experiments: 2-level factorial design + analysis."""
from __future__ import annotations
import uuid
import itertools
import numpy as np
import pandas as pd
import statsmodels.api as sm

from app.schemas.analysis import AnalysisRequest, AnalysisResult, TableSpec, ChartSpec
from app.utils.dataframe import payload_to_df
from app.services.analysis._common import (
    make_result, fmt, line_trace, scatter_trace, require_columns,
)


def run_factorial_design(req: AnalysisRequest) -> AnalysisResult:
    """Generate a 2^k full factorial design with replicates and randomization."""
    factors = req.params["factors"]  # list[{"name":..., "low":..., "high":...}]
    replicates = int(req.params.get("replicates", 1))
    randomize = bool(req.params.get("randomize", True))
    seed = req.params.get("seed", 42)

    if not factors or len(factors) < 2:
        raise ValueError("Need at least 2 factors for a factorial design.")

    levels = list(itertools.product([-1, 1], repeat=len(factors)))
    runs = []
    for _ in range(replicates):
        for combo in levels:
            row = {}
            for f, c in zip(factors, combo):
                row[f["name"]] = f["high"] if c == 1 else f["low"]
                row[f"{f['name']}_coded"] = c
            runs.append(row)

    order = list(range(len(runs)))
    if randomize:
        rng = np.random.default_rng(seed)
        rng.shuffle(order)
    table_rows = []
    for run_idx, original_idx in enumerate(order, start=1):
        r = runs[original_idx]
        table_rows.append([run_idx, original_idx + 1] +
                          [r[f["name"]] for f in factors] +
                          [r[f"{f['name']}_coded"] for f in factors])
    cols = ["run_order", "std_order"] + [f["name"] for f in factors] + [f"{f['name']}_coded" for f in factors]
    table = TableSpec(id=str(uuid.uuid4()), title=f"2^{len(factors)} factorial design", columns=cols, rows=table_rows)
    summary = f"Generated 2^{len(factors)} design with {replicates} replicate(s), {len(table_rows)} run(s)."
    return make_result(req, [table], [], summary)


def run_factorial_analyze(req: AnalysisRequest) -> AnalysisResult:
    """Analyze a factorial experiment via OLS with main effects + 2-way interactions."""
    df = payload_to_df(req.dataset)
    response = req.params["response"]
    factor_cols = list(req.params["factors"])
    require_columns(df, [response, *factor_cols])

    data = df[[response, *factor_cols]].copy()
    data[response] = pd.to_numeric(data[response], errors="coerce")
    # try numeric coding; else map two-level to -1/+1
    for fc in factor_cols:
        col = data[fc]
        if pd.api.types.is_numeric_dtype(col):
            uniq = np.sort(col.dropna().unique())
            if len(uniq) == 2:
                data[fc] = np.where(col == uniq[1], 1.0, -1.0)
            else:
                data[fc] = (col - col.mean()) / col.std(ddof=0).replace(0, 1) if hasattr(col, "replace") else col
        else:
            uniq = pd.Series(col.dropna().unique())
            if len(uniq) != 2:
                raise ValueError(f"Factor '{fc}' must have exactly 2 levels for 2k factorial.")
            data[fc] = np.where(col == uniq.iloc[1], 1.0, -1.0)
    data = data.dropna()

    X = data[factor_cols].copy()
    # add 2-way interactions
    inter_names = []
    for a, b in itertools.combinations(factor_cols, 2):
        name = f"{a}:{b}"
        X[name] = X[a] * X[b]
        inter_names.append(name)
    X = sm.add_constant(X, has_constant="add").astype(float)
    y = data[response].astype(float)
    model = sm.OLS(y, X).fit()

    effects = []
    for term in [t for t in model.params.index if t != "const"]:
        coef = model.params[term]
        effects.append([term, fmt(coef), fmt(2 * coef), fmt(model.bse[term]),
                        fmt(model.tvalues[term]), fmt(model.pvalues[term], 6)])
    eff_table = TableSpec(
        id=str(uuid.uuid4()), title="Estimated effects",
        columns=["term", "coefficient", "effect", "std_error", "t", "p_value"],
        rows=effects,
    )

    fit_table = TableSpec(
        id=str(uuid.uuid4()), title="Model fit",
        columns=["r_squared", "adj_r_squared", "F", "F_pvalue", "n"],
        rows=[[fmt(model.rsquared), fmt(model.rsquared_adj),
               fmt(model.fvalue), fmt(model.f_pvalue, 6), int(model.nobs)]],
    )

    # Main effects plot
    me_traces = []
    for fc in factor_cols:
        means = data.groupby(fc)[response].mean().sort_index()
        me_traces.append(line_trace(
            [f"{fc}={int(x)}" for x in means.index],
            means.values.tolist(),
            name=fc,
        ))
    me_chart = ChartSpec(
        id=str(uuid.uuid4()), title="Main effects", kind="effects",
        data=me_traces, layout={"yaxis": {"title": f"mean({response})"}},
    )

    # Interaction plot (first pair only for compactness)
    charts = [me_chart]
    if len(factor_cols) >= 2:
        a, b = factor_cols[0], factor_cols[1]
        traces = []
        for blev, sub in data.groupby(b):
            mean_a = sub.groupby(a)[response].mean().sort_index()
            traces.append(line_trace(
                [f"{a}={int(x)}" for x in mean_a.index],
                mean_a.values.tolist(),
                name=f"{b}={int(blev)}",
            ))
        charts.append(ChartSpec(
            id=str(uuid.uuid4()), title=f"Interaction: {a} x {b}", kind="interaction",
            data=traces, layout={"yaxis": {"title": f"mean({response})"}},
        ))

    summary = (
        f"Factorial analysis. R²={fmt(model.rsquared)}, "
        f"F={fmt(model.fvalue)}, p={fmt(model.f_pvalue,6)}, n={int(model.nobs)}."
    )
    return make_result(req, [eff_table, fit_table], charts, summary)
