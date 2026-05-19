"""Unit tests for each analysis service."""
import pytest

from app.schemas.analysis import AnalysisRequest
from app.services.analysis import REGISTRY


def _req(type_, dataset, params=None, options=None):
    return AnalysisRequest(type=type_, dataset=dataset, params=params or {}, options=options or {})


def test_descriptives_mtcars(mtcars):
    r = REGISTRY["descriptives"](_req("descriptives", mtcars, {"columns": ["mpg", "hp", "wt"]}))
    assert r.type == "descriptives"
    assert any(t.title.startswith("Descriptive") for t in r.statistical_tables)
    rows = r.statistical_tables[0].rows
    mpg_row = next(row for row in rows if row[0] == "mpg")
    # [variable, n, missing, mean, std, min, Q1, median, Q3, max]
    assert 19 < mpg_row[3] < 22  # mean mpg ~20


def test_descriptives_by_group(tooth_growth):
    r = REGISTRY["descriptives"](_req("descriptives", tooth_growth,
                                      {"columns": ["len"], "group_by": "supp"}))
    cols = r.statistical_tables[0].columns
    assert cols[1] == "group"


def test_ttest_one_sample(mtcars):
    r = REGISTRY["ttest_one_sample"](_req("ttest_one_sample", mtcars,
                                          {"column": "mpg", "mu0": 20.0}))
    assert len(r.statistical_tables) == 1


def test_ttest_two_sample(tooth_growth):
    r = REGISTRY["ttest_two_sample"](_req("ttest_two_sample", tooth_growth,
                                          {"value_column": "len", "group_column": "supp"}))
    cols = r.statistical_tables[0].columns
    assert "t" in cols and "p_value" in cols


def test_anova_tooth_growth(tooth_growth):
    r = REGISTRY["anova_one_way"](_req("anova_one_way", tooth_growth,
                                       {"response": "len", "factor": "supp"}))
    # ANOVA p-value should exist
    aov_rows = r.statistical_tables[0].rows
    assert aov_rows[0][4] is not None


def test_anova_three_groups_dose(tooth_growth):
    r = REGISTRY["anova_one_way"](_req("anova_one_way", tooth_growth,
                                       {"response": "len", "factor": "dose"}))
    p = r.statistical_tables[0].rows[0][4]
    assert p is not None and p < 0.05  # dose clearly affects tooth length


def test_regression_ols_mtcars(mtcars):
    r = REGISTRY["regression_ols"](_req("regression_ols", mtcars,
                                        {"response": "mpg", "predictors": ["wt", "hp"]}))
    fit = next(t for t in r.statistical_tables if t.title == "Model fit").rows[0]
    r2 = fit[0]
    assert 0.5 < r2 < 0.95  # mtcars wt+hp gives R² ~0.83


def test_logistic_iris_binary(iris):
    # binary: setosa vs not-setosa (separable!)
    payload = iris.model_copy(deep=True)
    for row in payload.rows:
        row["target"] = 1 if row.get("species") == "versicolor" else 0
    payload.columns.append(type(payload.columns[0])(name="target", type="integer", n_missing=0))
    r = REGISTRY["regression_logistic"](_req("regression_logistic", payload,
                                             {"response": "target",
                                              "predictors": ["sepal_length", "petal_length"]}))
    fit = next(t for t in r.statistical_tables if t.title == "Model fit").rows[0]
    assert fit[4] is not None  # accuracy reported


def test_pca_usarrests(usarrests):
    r = REGISTRY["pca"](_req("pca", usarrests,
                             {"columns": ["Murder", "Assault", "UrbanPop", "Rape"],
                              "n_components": 2}))
    var_tbl = r.statistical_tables[0]
    pc1_ratio = var_tbl.rows[0][2]
    assert pc1_ratio > 0.5


def test_kmeans_iris(iris):
    r = REGISTRY["kmeans"](_req("kmeans", iris,
                                {"columns": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
                                 "k": 3}))
    sizes_table = r.statistical_tables[0]
    assert sum(row[1] for row in sizes_table.rows) == 150


def test_control_chart_imr(spc):
    # individuals chart on first 25 obs flattened
    payload = spc
    r = REGISTRY["control_chart_imr"](_req("control_chart_imr", payload,
                                            {"column": "fill_ml"}))
    assert any(t.title.startswith("I-MR") for t in r.statistical_tables)


def test_control_chart_xbar_r(spc):
    r = REGISTRY["control_chart_xbar_r"](_req("control_chart_xbar_r", spc,
                                               {"column": "fill_ml", "subgroup_column": "subgroup"}))
    assert any(t.title.startswith("Xbar-R") for t in r.statistical_tables)


def test_doe_design():
    from app.schemas.dataset import DatasetPayload
    empty = DatasetPayload(name="empty", columns=[], rows=[], row_ids=[])
    r = REGISTRY["doe_factorial_design"](_req("doe_factorial_design", empty,
                                              {"factors": [
                                                  {"name": "A", "low": 0, "high": 1},
                                                  {"name": "B", "low": 10, "high": 20},
                                                  {"name": "C", "low": -1, "high": 1},
                                              ], "replicates": 2}))
    assert len(r.statistical_tables[0].rows) == 16


def test_doe_analyze(doe):
    r = REGISTRY["doe_factorial_analyze"](_req("doe_factorial_analyze", doe,
                                                {"response": "yield", "factors": ["A", "B", "C"]}))
    # main effect of A should be largest and significant
    rows = r.statistical_tables[0].rows
    a_row = next(row for row in rows if row[0] == "A")
    assert abs(a_row[2]) > abs(next(row for row in rows if row[0] == "C")[2])


def test_chi_square(tooth_growth):
    r = REGISTRY["chi_square"](_req("chi_square", tooth_growth,
                                    {"column_a": "supp", "column_b": "dose"}))
    assert any(t.title.startswith("Chi-square") for t in r.statistical_tables)


def test_timeseries_forecast(air_passengers):
    r = REGISTRY["timeseries_forecast"](_req("timeseries_forecast", air_passengers,
                                              {"value_column": "passengers", "time_column": "month",
                                               "horizon": 12, "method": "ets", "period": 12}))
    fcst = r.statistical_tables[0].rows
    assert len(fcst) == 12
