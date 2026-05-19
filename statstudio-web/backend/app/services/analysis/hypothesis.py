"""Hypothesis tests: t-tests, chi-square, proportion test."""
from __future__ import annotations
import uuid
import numpy as np
import pandas as pd
from scipy import stats

from app.schemas.analysis import AnalysisRequest, AnalysisResult, TableSpec, ChartSpec
from app.utils.dataframe import payload_to_df
from app.services.analysis._common import (
    make_result, fmt, histogram_trace, box_trace, require_columns, safe_series,
)


def run_ttest_one_sample(req: AnalysisRequest) -> AnalysisResult:
    df = payload_to_df(req.dataset)
    col = req.params["column"]
    mu0 = float(req.params.get("mu0", 0))
    alt = req.params.get("alternative", "two-sided")
    require_columns(df, [col])
    s = safe_series(df[col])
    if len(s) < 2:
        raise ValueError("Need at least 2 non-missing observations.")
    t, p = stats.ttest_1samp(s, popmean=mu0, alternative=alt)
    n = len(s)
    mean = s.mean()
    se = s.std(ddof=1) / np.sqrt(n)
    ci_low, ci_high = stats.t.interval(0.95, df=n - 1, loc=mean, scale=se)
    table = TableSpec(
        id=str(uuid.uuid4()),
        title="One-sample t-test",
        columns=["statistic", "df", "p_value", "mean", "se", "ci_low", "ci_high", "mu0", "alternative"],
        rows=[[fmt(t), n - 1, fmt(p, 6), fmt(mean), fmt(se), fmt(ci_low), fmt(ci_high), mu0, alt]],
    )
    charts = [
        ChartSpec(
            id=str(uuid.uuid4()),
            title=f"Histogram - {col}",
            kind="histogram",
            data=[histogram_trace(s.values, name=col)],
            layout={"shapes": [{"type": "line", "x0": mu0, "x1": mu0, "yref": "paper", "y0": 0, "y1": 1,
                                "line": {"color": "red", "dash": "dash"}}],
                    "xaxis": {"title": col}, "yaxis": {"title": "count"}},
        )
    ]
    summary = f"Mean={fmt(mean)}, t={fmt(t)}, p={fmt(p,6)} (H0: mu={mu0}, alt={alt})."
    return make_result(req, [table], charts, summary)


def run_ttest_two_sample(req: AnalysisRequest) -> AnalysisResult:
    df = payload_to_df(req.dataset)
    value_col = req.params["value_column"]
    group_col = req.params["group_column"]
    equal_var = bool(req.params.get("equal_var", False))
    alt = req.params.get("alternative", "two-sided")
    require_columns(df, [value_col, group_col])

    groups = list(df[group_col].dropna().unique())
    if len(groups) != 2:
        raise ValueError(f"Two-sample t-test needs exactly 2 groups; found {len(groups)}.")
    a = safe_series(df.loc[df[group_col] == groups[0], value_col])
    b = safe_series(df.loc[df[group_col] == groups[1], value_col])
    if len(a) < 2 or len(b) < 2:
        raise ValueError("Each group needs at least 2 observations.")
    t, p = stats.ttest_ind(a, b, equal_var=equal_var, alternative=alt)
    table = TableSpec(
        id=str(uuid.uuid4()),
        title="Two-sample t-test",
        columns=["group_a", "n_a", "mean_a", "std_a", "group_b", "n_b", "mean_b", "std_b",
                 "t", "p_value", "equal_var", "alternative"],
        rows=[[str(groups[0]), len(a), fmt(a.mean()), fmt(a.std(ddof=1)),
               str(groups[1]), len(b), fmt(b.mean()), fmt(b.std(ddof=1)),
               fmt(t), fmt(p, 6), equal_var, alt]],
    )
    charts = [
        ChartSpec(
            id=str(uuid.uuid4()),
            title=f"Boxplot of {value_col} by {group_col}",
            kind="boxplot",
            data=[box_trace(a.values, name=str(groups[0])), box_trace(b.values, name=str(groups[1]))],
            layout={"yaxis": {"title": value_col}},
        )
    ]
    summary = f"t={fmt(t)}, p={fmt(p,6)} (equal_var={equal_var}, alt={alt})."
    return make_result(req, [table], charts, summary)


def run_ttest_paired(req: AnalysisRequest) -> AnalysisResult:
    df = payload_to_df(req.dataset)
    a_col = req.params["column_a"]
    b_col = req.params["column_b"]
    alt = req.params.get("alternative", "two-sided")
    require_columns(df, [a_col, b_col])
    pair = df[[a_col, b_col]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(pair) < 2:
        raise ValueError("Need at least 2 non-missing paired observations.")
    t, p = stats.ttest_rel(pair[a_col], pair[b_col], alternative=alt)
    diff = pair[a_col] - pair[b_col]
    table = TableSpec(
        id=str(uuid.uuid4()),
        title="Paired t-test",
        columns=["n", "mean_diff", "std_diff", "t", "p_value", "alternative"],
        rows=[[len(pair), fmt(diff.mean()), fmt(diff.std(ddof=1)), fmt(t), fmt(p, 6), alt]],
    )
    charts = [
        ChartSpec(
            id=str(uuid.uuid4()),
            title="Histogram of differences",
            kind="histogram",
            data=[histogram_trace(diff.values, name="diff")],
            layout={"xaxis": {"title": f"{a_col} - {b_col}"}},
        )
    ]
    return make_result(req, [table], charts, f"t={fmt(t)}, p={fmt(p,6)}.")


def run_chi_square(req: AnalysisRequest) -> AnalysisResult:
    df = payload_to_df(req.dataset)
    a = req.params["column_a"]
    b = req.params["column_b"]
    require_columns(df, [a, b])
    tbl = pd.crosstab(df[a], df[b])
    if tbl.size == 0:
        raise ValueError("Empty contingency table.")
    chi2, p, dof, expected = stats.chi2_contingency(tbl.values)
    ctable = TableSpec(
        id=str(uuid.uuid4()),
        title=f"Contingency table: {a} x {b}",
        columns=["row", *[str(c) for c in tbl.columns]],
        rows=[[str(idx), *[int(v) for v in row]] for idx, row in zip(tbl.index, tbl.values)],
    )
    stat_table = TableSpec(
        id=str(uuid.uuid4()),
        title="Chi-square test of independence",
        columns=["chi2", "df", "p_value"],
        rows=[[fmt(chi2), int(dof), fmt(p, 6)]],
    )
    return make_result(req, [ctable, stat_table], [], f"chi2={fmt(chi2)}, df={dof}, p={fmt(p,6)}.")


def run_proportion_test(req: AnalysisRequest) -> AnalysisResult:
    """Two-proportion z-test (or one-proportion via binomial)."""
    df = payload_to_df(req.dataset)
    col = req.params["column"]
    success_value = req.params.get("success_value")
    group_col = req.params.get("group_column")
    require_columns(df, [col])
    if group_col:
        require_columns(df, [group_col])
        groups = list(df[group_col].dropna().unique())
        if len(groups) != 2:
            raise ValueError("Two-proportion test needs exactly 2 groups.")
        from statsmodels.stats.proportion import proportions_ztest
        counts = []
        nobs = []
        for g in groups:
            sub = df.loc[df[group_col] == g, col].dropna()
            counts.append(int((sub == success_value).sum()))
            nobs.append(int(len(sub)))
        z, p = proportions_ztest(counts, nobs)
        rows = [[str(groups[0]), counts[0], nobs[0], fmt(counts[0] / nobs[0]),
                 str(groups[1]), counts[1], nobs[1], fmt(counts[1] / nobs[1]),
                 fmt(z), fmt(p, 6)]]
        table = TableSpec(id=str(uuid.uuid4()), title="Two-proportion z-test",
                          columns=["group_a", "x_a", "n_a", "p_a", "group_b", "x_b", "n_b", "p_b", "z", "p_value"],
                          rows=rows)
        return make_result(req, [table], [], f"z={fmt(z)}, p={fmt(p,6)}.")
    else:
        s = df[col].dropna()
        x = int((s == success_value).sum())
        n = int(len(s))
        p0 = float(req.params.get("p0", 0.5))
        res = stats.binomtest(x, n, p=p0, alternative=req.params.get("alternative", "two-sided"))
        table = TableSpec(id=str(uuid.uuid4()), title="One-proportion test (binomial)",
                          columns=["x", "n", "p_hat", "p0", "p_value"],
                          rows=[[x, n, fmt(x / n if n else None), p0, fmt(res.pvalue, 6)]])
        return make_result(req, [table], [], f"p_hat={fmt(x/n if n else None)}, p={fmt(res.pvalue,6)}.")
