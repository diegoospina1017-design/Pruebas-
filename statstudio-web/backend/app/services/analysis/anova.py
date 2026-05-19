"""One-way ANOVA with Tukey HSD post-hoc."""
from __future__ import annotations
import uuid
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
from statsmodels.formula.api import ols
from statsmodels.stats.multicomp import pairwise_tukeyhsd

from app.schemas.analysis import AnalysisRequest, AnalysisResult, TableSpec, ChartSpec
from app.utils.dataframe import payload_to_df
from app.services.analysis._common import make_result, fmt, box_trace, require_columns


def run_anova_one_way(req: AnalysisRequest) -> AnalysisResult:
    df = payload_to_df(req.dataset)
    response = req.params["response"]
    factor = req.params["factor"]
    require_columns(df, [response, factor])

    data = df[[response, factor]].copy()
    data[response] = pd.to_numeric(data[response], errors="coerce")
    data = data.dropna()
    if data[factor].nunique() < 2:
        raise ValueError("ANOVA requires at least 2 groups.")

    # Build via formula safe-by-Q()
    formula = f"Q('{response}') ~ C(Q('{factor}'))"
    model = ols(formula, data=data).fit()
    aov = sm.stats.anova_lm(model, typ=2)

    aov_table = TableSpec(
        id=str(uuid.uuid4()),
        title=f"One-way ANOVA: {response} ~ {factor}",
        columns=["source", "sum_sq", "df", "F", "p_value"],
        rows=[
            [str(idx), fmt(row["sum_sq"]), fmt(row["df"]), fmt(row.get("F")), fmt(row.get("PR(>F)"), 6)]
            for idx, row in aov.iterrows()
        ],
    )

    # group means
    group_table = TableSpec(
        id=str(uuid.uuid4()),
        title="Group statistics",
        columns=["group", "n", "mean", "std"],
        rows=[
            [str(g), int(len(sub)), fmt(sub[response].mean()), fmt(sub[response].std(ddof=1))]
            for g, sub in data.groupby(factor)
        ],
    )

    # Tukey HSD
    tukey_rows = []
    try:
        tk = pairwise_tukeyhsd(endog=data[response], groups=data[factor].astype(str), alpha=0.05)
        for r in tk.summary().data[1:]:
            tukey_rows.append([str(r[0]), str(r[1]), fmt(r[2]), fmt(r[3], 6), fmt(r[4]), fmt(r[5]), bool(r[6])])
        tukey_table = TableSpec(
            id=str(uuid.uuid4()),
            title="Tukey HSD pairwise comparisons",
            columns=["group1", "group2", "mean_diff", "p_adj", "lower", "upper", "reject"],
            rows=tukey_rows,
        )
    except Exception as e:
        tukey_table = TableSpec(
            id=str(uuid.uuid4()),
            title="Tukey HSD pairwise comparisons",
            columns=["info"],
            rows=[[f"Tukey HSD unavailable: {e}"]],
        )

    charts = [
        ChartSpec(
            id=str(uuid.uuid4()),
            title=f"{response} by {factor}",
            kind="boxplot",
            data=[box_trace(sub[response].values, name=str(g)) for g, sub in data.groupby(factor)],
            layout={"yaxis": {"title": response}, "xaxis": {"title": factor}},
        )
    ]

    F = aov.iloc[0].get("F")
    p = aov.iloc[0].get("PR(>F)")
    summary = f"F={fmt(F)}, p={fmt(p,6)} across {data[factor].nunique()} groups."
    return make_result(req, [aov_table, group_table, tukey_table], charts, summary)
