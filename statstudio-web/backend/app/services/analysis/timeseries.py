"""Time series: summary, decomposition, ACF/PACF, forecast."""
from __future__ import annotations
import uuid
import numpy as np
import pandas as pd

from app.schemas.analysis import AnalysisRequest, AnalysisResult, TableSpec, ChartSpec
from app.utils.dataframe import payload_to_df
from app.services.analysis._common import make_result, fmt, line_trace, require_columns


def _as_series(df: pd.DataFrame, value_col: str, time_col: str | None):
    if time_col and time_col in df.columns:
        idx = pd.to_datetime(df[time_col], errors="coerce")
        s = pd.Series(pd.to_numeric(df[value_col], errors="coerce").values, index=idx)
    else:
        s = pd.Series(pd.to_numeric(df[value_col], errors="coerce").values)
    s = s.dropna()
    s.name = value_col
    return s


def run_timeseries_summary(req: AnalysisRequest) -> AnalysisResult:
    df = payload_to_df(req.dataset)
    value_col = req.params["value_column"]
    time_col = req.params.get("time_column")
    period = req.params.get("period")
    require_columns(df, [value_col])
    s = _as_series(df, value_col, time_col)
    if s.empty:
        raise ValueError("Empty time series.")

    x_axis = [str(x) for x in s.index.tolist()]
    charts = [ChartSpec(
        id=str(uuid.uuid4()), title=f"Series - {value_col}", kind="line",
        data=[line_trace(x_axis, s.values, name=value_col)],
        layout={"xaxis": {"title": "time"}, "yaxis": {"title": value_col}},
    )]

    tables: list[TableSpec] = []
    warnings: list[str] = []

    # decomposition
    try:
        from statsmodels.tsa.seasonal import seasonal_decompose
        p = int(period) if period else None
        if p is None:
            p = _infer_period(s)
        if p and len(s) >= 2 * p:
            dec = seasonal_decompose(s, model="additive", period=p, extrapolate_trend="freq")
            charts.append(ChartSpec(
                id=str(uuid.uuid4()), title=f"Trend (period={p})", kind="line",
                data=[line_trace(x_axis, dec.trend.values, name="trend")],
            ))
            charts.append(ChartSpec(
                id=str(uuid.uuid4()), title="Seasonal", kind="line",
                data=[line_trace(x_axis, dec.seasonal.values, name="seasonal")],
            ))
            charts.append(ChartSpec(
                id=str(uuid.uuid4()), title="Residual", kind="line",
                data=[line_trace(x_axis, dec.resid.values, name="residual")],
            ))
        else:
            warnings.append("Decomposition skipped: insufficient data for the chosen period.")
    except Exception as e:
        warnings.append(f"Decomposition failed: {e}")

    # ACF/PACF
    try:
        from statsmodels.tsa.stattools import acf, pacf
        nlags = int(min(40, len(s) // 2 - 1))
        if nlags >= 2:
            ac = acf(s.values, nlags=nlags, fft=True)
            pc = pacf(s.values, nlags=nlags)
            tables.append(TableSpec(
                id=str(uuid.uuid4()), title="ACF / PACF",
                columns=["lag", "ACF", "PACF"],
                rows=[[i, fmt(ac[i]), fmt(pc[i])] for i in range(len(ac))],
            ))
    except Exception as e:
        warnings.append(f"ACF/PACF failed: {e}")

    summary = f"Series length n={len(s)}, mean={fmt(s.mean())}, std={fmt(s.std(ddof=1))}."
    return make_result(req, tables, charts, summary, warnings=warnings)


def run_timeseries_forecast(req: AnalysisRequest) -> AnalysisResult:
    df = payload_to_df(req.dataset)
    value_col = req.params["value_column"]
    time_col = req.params.get("time_column")
    horizon = int(req.params.get("horizon", 12))
    method = req.params.get("method", "ets")  # 'ets' or 'arima'
    period = req.params.get("period")
    require_columns(df, [value_col])

    s = _as_series(df, value_col, time_col)
    if len(s) < 6:
        raise ValueError("Need at least 6 observations to forecast.")

    p = int(period) if period else _infer_period(s) or 1
    fitted = None
    fcst = None
    ci = None
    used_method = method

    try:
        if method == "arima":
            from statsmodels.tsa.arima.model import ARIMA
            order = tuple(req.params.get("order", (1, 1, 1)))
            res = ARIMA(s, order=order).fit()
            fitted = res.fittedvalues
            forecast_obj = res.get_forecast(steps=horizon)
            fcst = forecast_obj.predicted_mean
            ci = forecast_obj.conf_int(alpha=0.05)
        else:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing
            seasonal = "add" if p and p > 1 and len(s) >= 2 * p else None
            res = ExponentialSmoothing(
                s.astype(float), trend="add", seasonal=seasonal,
                seasonal_periods=p if seasonal else None,
                initialization_method="estimated",
            ).fit()
            fitted = res.fittedvalues
            fcst = res.forecast(horizon)
            ci = None
            used_method = f"ets(period={p})"
    except Exception as e:
        raise ValueError(f"Forecast failed ({method}): {e}")

    x_hist = [str(x) for x in s.index.tolist()]
    x_fcst = [str(x) for x in fcst.index.tolist()]

    traces = [
        line_trace(x_hist, s.values, name="observed"),
        line_trace(x_hist, fitted.values, name="fitted"),
        line_trace(x_fcst, fcst.values, name="forecast"),
    ]
    if ci is not None:
        traces.append(line_trace(x_fcst, ci.iloc[:, 0].values, name="ci_low"))
        traces.append(line_trace(x_fcst, ci.iloc[:, 1].values, name="ci_high"))

    chart = ChartSpec(
        id=str(uuid.uuid4()), title=f"Forecast ({used_method}), horizon={horizon}", kind="line",
        data=traces, layout={"xaxis": {"title": "time"}, "yaxis": {"title": value_col}},
    )
    table = TableSpec(
        id=str(uuid.uuid4()), title="Forecast",
        columns=["time", "forecast"] + (["ci_low", "ci_high"] if ci is not None else []),
        rows=[
            [x_fcst[i], fmt(float(fcst.values[i]))] +
            ([fmt(float(ci.iloc[i, 0])), fmt(float(ci.iloc[i, 1]))] if ci is not None else [])
            for i in range(len(fcst))
        ],
    )
    return make_result(
        req, [table], [chart],
        f"Forecast generated with {used_method} for horizon={horizon}.",
    )


def _infer_period(s: pd.Series) -> int | None:
    if isinstance(s.index, pd.DatetimeIndex) and s.index.freq is not None:
        freq = s.index.inferred_freq or s.index.freqstr or ""
        f = freq.upper()
        if f.startswith(("M", "MS")):
            return 12
        if f.startswith("Q"):
            return 4
        if f.startswith("W"):
            return 52
        if f.startswith("D"):
            return 7
    return None
