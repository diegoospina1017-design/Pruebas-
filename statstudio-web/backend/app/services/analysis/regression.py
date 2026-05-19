"""Linear (OLS) and logistic regression."""
from __future__ import annotations
import uuid
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats as sstats
from sklearn.metrics import (
    accuracy_score, confusion_matrix, roc_auc_score,
)

from app.schemas.analysis import AnalysisRequest, AnalysisResult, TableSpec, ChartSpec
from app.utils.dataframe import payload_to_df
from app.services.analysis._common import (
    make_result, fmt, scatter_trace, line_trace, require_columns,
)


def _build_design(df: pd.DataFrame, response: str, predictors: list[str]):
    data = df[[response] + predictors].copy()
    # coerce response to numeric; leave predictors as-is so categoricals can be one-hot encoded later
    data[response] = pd.to_numeric(data[response], errors="coerce")
    data = data.dropna()
    if data.empty:
        raise ValueError("No complete observations available.")
    y = pd.to_numeric(data[response], errors="coerce")
    X = data[predictors].copy()
    # one-hot encode non-numeric predictors
    X = pd.get_dummies(X, drop_first=True)
    # ensure numeric matrix
    X = X.apply(pd.to_numeric, errors="coerce").dropna(axis=0)
    y = y.loc[X.index].dropna()
    X = X.loc[y.index]
    X = sm.add_constant(X, has_constant="add")
    X = X.astype(float)
    y = y.astype(float)
    return y, X, data.loc[X.index]


def run_regression_ols(req: AnalysisRequest) -> AnalysisResult:
    df = payload_to_df(req.dataset)
    response = req.params["response"]
    predictors = list(req.params["predictors"])
    require_columns(df, [response, *predictors])

    y, X, data = _build_design(df, response, predictors)
    model = sm.OLS(y, X).fit()

    coef_rows = []
    conf = model.conf_int(0.05)
    for name, coef in model.params.items():
        coef_rows.append([
            name,
            fmt(coef),
            fmt(model.bse[name]),
            fmt(model.tvalues[name]),
            fmt(model.pvalues[name], 6),
            fmt(conf.loc[name, 0]),
            fmt(conf.loc[name, 1]),
        ])
    coef_table = TableSpec(
        id=str(uuid.uuid4()),
        title="OLS coefficients",
        columns=["term", "estimate", "std_error", "t", "p_value", "ci_low", "ci_high"],
        rows=coef_rows,
    )

    fit_table = TableSpec(
        id=str(uuid.uuid4()),
        title="Model fit",
        columns=["r_squared", "adj_r_squared", "F", "F_pvalue", "AIC", "BIC", "n", "df_resid"],
        rows=[[
            fmt(model.rsquared), fmt(model.rsquared_adj),
            fmt(model.fvalue), fmt(model.f_pvalue, 6),
            fmt(model.aic), fmt(model.bic),
            int(model.nobs), int(model.df_resid),
        ]],
    )

    fitted = model.fittedvalues
    resid = model.resid
    row_ids = [str(i) for i in data.index.tolist()]

    charts = [
        ChartSpec(
            id=str(uuid.uuid4()),
            title="Residuals vs Fitted",
            kind="residuals",
            data=[scatter_trace(fitted.values, resid.values, name="residuals", row_ids=row_ids)],
            layout={"xaxis": {"title": "Fitted"}, "yaxis": {"title": "Residual"},
                    "shapes": [{"type": "line", "x0": float(fitted.min()), "x1": float(fitted.max()),
                                "y0": 0, "y1": 0, "line": {"color": "red", "dash": "dash"}}]},
            row_ids=row_ids,
        ),
        _qq_chart(resid.values),
    ]
    if len(predictors) == 1 and pd.api.types.is_numeric_dtype(df[predictors[0]]):
        xv = data[predictors[0]].values
        order = np.argsort(xv)
        charts.append(
            ChartSpec(
                id=str(uuid.uuid4()),
                title=f"{response} vs {predictors[0]}",
                kind="scatter",
                data=[
                    scatter_trace(xv, y.values, name="data", row_ids=row_ids),
                    line_trace(xv[order], fitted.values[order], name="fit"),
                ],
                layout={"xaxis": {"title": predictors[0]}, "yaxis": {"title": response}},
                row_ids=row_ids,
            )
        )

    summary = (
        f"OLS: R²={fmt(model.rsquared)} (adj {fmt(model.rsquared_adj)}), "
        f"F={fmt(model.fvalue)}, p={fmt(model.f_pvalue,6)}, n={int(model.nobs)}."
    )
    return make_result(req, [coef_table, fit_table], charts, summary)


def _qq_chart(resid: np.ndarray) -> ChartSpec:
    osm, osr = sstats.probplot(resid, dist="norm", fit=False)
    slope, intercept, _ = sstats.linregress(osm, osr)[:3]
    x = np.array([osm.min(), osm.max()])
    return ChartSpec(
        id=str(uuid.uuid4()),
        title="Q-Q plot of residuals",
        kind="qq",
        data=[
            scatter_trace(osm, osr, name="quantiles"),
            line_trace(x, slope * x + intercept, name="reference"),
        ],
        layout={"xaxis": {"title": "Theoretical quantiles"}, "yaxis": {"title": "Sample quantiles"}},
    )


def run_regression_logistic(req: AnalysisRequest) -> AnalysisResult:
    df = payload_to_df(req.dataset)
    response = req.params["response"]
    predictors = list(req.params["predictors"])
    require_columns(df, [response, *predictors])

    data = df[[response] + predictors].dropna()
    y_raw = data[response]
    # binarize: numeric 0/1 or any 2-level factor
    unique = pd.Series(y_raw.unique()).dropna()
    if len(unique) != 2:
        raise ValueError("Logistic regression requires a binary response (2 unique values).")
    pos_label = req.params.get("positive_class", str(sorted(unique.astype(str))[1]))
    y = (y_raw.astype(str) == str(pos_label)).astype(int)

    X = pd.get_dummies(data[predictors], drop_first=True).apply(pd.to_numeric, errors="coerce")
    keep = X.dropna().index
    X = sm.add_constant(X.loc[keep], has_constant="add").astype(float)
    y = y.loc[keep].astype(int)

    model = sm.Logit(y, X).fit(disp=False)

    coef_rows = []
    conf = model.conf_int(0.05)
    for name, coef in model.params.items():
        coef_rows.append([
            name, fmt(coef), fmt(np.exp(coef)),
            fmt(model.bse[name]), fmt(model.tvalues[name]),
            fmt(model.pvalues[name], 6),
            fmt(conf.loc[name, 0]), fmt(conf.loc[name, 1]),
        ])
    coef_table = TableSpec(
        id=str(uuid.uuid4()),
        title="Logistic regression coefficients",
        columns=["term", "estimate", "odds_ratio", "std_error", "z", "p_value", "ci_low", "ci_high"],
        rows=coef_rows,
    )

    preds_p = model.predict(X).values
    preds_cls = (preds_p >= 0.5).astype(int)
    acc = accuracy_score(y, preds_cls)
    try:
        auc = roc_auc_score(y, preds_p)
    except Exception:
        auc = None
    cm = confusion_matrix(y, preds_cls).tolist()

    fit_table = TableSpec(
        id=str(uuid.uuid4()),
        title="Model fit",
        columns=["pseudo_r2", "log_likelihood", "AIC", "BIC", "accuracy", "auc", "n"],
        rows=[[fmt(model.prsquared), fmt(model.llf), fmt(model.aic), fmt(model.bic),
               fmt(acc), fmt(auc) if auc is not None else None, int(model.nobs)]],
    )
    cm_table = TableSpec(
        id=str(uuid.uuid4()),
        title="Confusion matrix (threshold=0.5)",
        columns=["actual\\predicted", "0", "1"],
        rows=[["0", int(cm[0][0]), int(cm[0][1])], ["1", int(cm[1][0]), int(cm[1][1])]],
    )

    # ROC
    charts: list[ChartSpec] = []
    if auc is not None:
        try:
            from sklearn.metrics import roc_curve
            fpr, tpr, _ = roc_curve(y, preds_p)
            charts.append(ChartSpec(
                id=str(uuid.uuid4()), title=f"ROC (AUC={fmt(auc)})", kind="line",
                data=[
                    line_trace(fpr, tpr, name="ROC"),
                    line_trace([0, 1], [0, 1], name="chance"),
                ],
                layout={"xaxis": {"title": "FPR"}, "yaxis": {"title": "TPR"}},
            ))
        except Exception:
            pass

    summary = f"Logit fitted. Accuracy={fmt(acc)}, AUC={fmt(auc) if auc is not None else 'NA'}."
    return make_result(req, [coef_table, fit_table, cm_table], charts, summary)
