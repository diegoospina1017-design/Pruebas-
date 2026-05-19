"""Analysis service registry."""
from app.services.analysis.descriptives import run_descriptives
from app.services.analysis.hypothesis import (
    run_ttest_one_sample,
    run_ttest_two_sample,
    run_ttest_paired,
    run_chi_square,
    run_proportion_test,
)
from app.services.analysis.anova import run_anova_one_way
from app.services.analysis.regression import run_regression_ols, run_regression_logistic
from app.services.analysis.timeseries import run_timeseries_summary, run_timeseries_forecast
from app.services.analysis.control_charts import run_imr_chart, run_xbar_r_chart
from app.services.analysis.doe import run_factorial_design, run_factorial_analyze
from app.services.analysis.multivariate import run_pca, run_kmeans, run_hclust

REGISTRY = {
    "descriptives": run_descriptives,
    "ttest_one_sample": run_ttest_one_sample,
    "ttest_two_sample": run_ttest_two_sample,
    "ttest_paired": run_ttest_paired,
    "chi_square": run_chi_square,
    "proportion_test": run_proportion_test,
    "anova_one_way": run_anova_one_way,
    "regression_ols": run_regression_ols,
    "regression_logistic": run_regression_logistic,
    "timeseries_summary": run_timeseries_summary,
    "timeseries_forecast": run_timeseries_forecast,
    "control_chart_imr": run_imr_chart,
    "control_chart_xbar_r": run_xbar_r_chart,
    "doe_factorial_design": run_factorial_design,
    "doe_factorial_analyze": run_factorial_analyze,
    "pca": run_pca,
    "kmeans": run_kmeans,
    "hclust": run_hclust,
}
