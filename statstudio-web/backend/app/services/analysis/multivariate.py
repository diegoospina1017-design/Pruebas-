"""Multivariate analysis: PCA, k-means, hierarchical clustering."""
from __future__ import annotations
import uuid
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans, AgglomerativeClustering
from scipy.cluster.hierarchy import linkage, fcluster

from app.schemas.analysis import AnalysisRequest, AnalysisResult, TableSpec, ChartSpec
from app.utils.dataframe import payload_to_df, numeric_columns
from app.services.analysis._common import make_result, fmt, scatter_trace, line_trace, require_columns


def _numeric_matrix(df: pd.DataFrame, cols: list[str], scale: bool = True):
    sub = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    if sub.empty:
        raise ValueError("No complete observations available for the chosen columns.")
    X = sub.values.astype(float)
    if scale:
        X = StandardScaler().fit_transform(X)
    return X, sub.index.tolist(), sub


def run_pca(req: AnalysisRequest) -> AnalysisResult:
    df = payload_to_df(req.dataset)
    cols = req.params.get("columns") or numeric_columns(df)
    n_components = int(req.params.get("n_components", min(len(cols), 5)))
    scale = bool(req.params.get("scale", True))
    require_columns(df, cols)
    if len(cols) < 2:
        raise ValueError("PCA needs at least 2 numeric columns.")

    X, row_ids, sub = _numeric_matrix(df, cols, scale=scale)
    n_components = min(n_components, X.shape[1], X.shape[0])
    pca = PCA(n_components=n_components)
    scores = pca.fit_transform(X)
    evr = pca.explained_variance_ratio_

    pc_cols = [f"PC{i+1}" for i in range(n_components)]
    loadings = pca.components_.T  # shape (features, components)

    var_table = TableSpec(
        id=str(uuid.uuid4()), title="Variance explained",
        columns=["component", "eigenvalue", "var_ratio", "cum_var_ratio"],
        rows=[[pc_cols[i], fmt(pca.explained_variance_[i]), fmt(evr[i]), fmt(np.cumsum(evr)[i])]
              for i in range(n_components)],
    )
    loadings_table = TableSpec(
        id=str(uuid.uuid4()), title="Loadings",
        columns=["variable", *pc_cols],
        rows=[[cols[i], *[fmt(v) for v in loadings[i].tolist()]] for i in range(len(cols))],
    )

    scree = ChartSpec(
        id=str(uuid.uuid4()), title="Scree plot", kind="scree",
        data=[
            line_trace(pc_cols, evr.tolist(), name="var_ratio"),
        ],
        layout={"xaxis": {"title": "component"}, "yaxis": {"title": "variance ratio"}},
    )

    charts = [scree]
    if n_components >= 2:
        charts.append(ChartSpec(
            id=str(uuid.uuid4()), title="PCA scores (PC1 vs PC2)", kind="scatter",
            data=[scatter_trace(scores[:, 0], scores[:, 1], name="scores",
                                row_ids=[str(i) for i in row_ids])],
            layout={"xaxis": {"title": "PC1"}, "yaxis": {"title": "PC2"}},
            row_ids=[str(i) for i in row_ids],
        ))
        # Biplot (loadings overlaid)
        biplot_traces = [
            scatter_trace(scores[:, 0], scores[:, 1], name="scores",
                          row_ids=[str(i) for i in row_ids]),
        ]
        scale_factor = float(np.max(np.abs(scores[:, :2])) / max(np.abs(loadings[:, :2]).max(), 1e-9))
        for i, name in enumerate(cols):
            biplot_traces.append({
                "type": "scatter", "mode": "lines+text",
                "x": [0, loadings[i, 0] * scale_factor],
                "y": [0, loadings[i, 1] * scale_factor],
                "text": ["", name],
                "textposition": "top center",
                "name": name,
                "line": {"color": "red"},
                "showlegend": False,
            })
        charts.append(ChartSpec(
            id=str(uuid.uuid4()), title="Biplot", kind="biplot",
            data=biplot_traces,
            layout={"xaxis": {"title": "PC1"}, "yaxis": {"title": "PC2"}},
            row_ids=[str(i) for i in row_ids],
        ))

    summary = f"PCA on {len(cols)} variables. PC1 explains {fmt(evr[0]*100,2)}%, cum to PC{n_components}: {fmt(np.cumsum(evr)[-1]*100,2)}%."
    return make_result(req, [var_table, loadings_table], charts, summary)


def run_kmeans(req: AnalysisRequest) -> AnalysisResult:
    df = payload_to_df(req.dataset)
    cols = req.params.get("columns") or numeric_columns(df)
    k = int(req.params.get("k", 3))
    scale = bool(req.params.get("scale", True))
    seed = int(req.params.get("seed", 42))
    require_columns(df, cols)
    if len(cols) < 2:
        raise ValueError("K-means needs at least 2 numeric columns.")

    X, row_ids, sub = _numeric_matrix(df, cols, scale=scale)
    if k > len(X):
        raise ValueError(f"k={k} exceeds number of rows ({len(X)}).")
    km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(X)
    labels = km.labels_

    cluster_table = TableSpec(
        id=str(uuid.uuid4()), title="Cluster sizes",
        columns=["cluster", "n"],
        rows=[[int(c), int((labels == c).sum())] for c in range(k)],
    )
    centroids_table = TableSpec(
        id=str(uuid.uuid4()), title="Centroids (in scaled space)" if scale else "Centroids",
        columns=["cluster", *cols],
        rows=[[int(c), *[fmt(v) for v in km.cluster_centers_[c]]] for c in range(k)],
    )

    charts: list[ChartSpec] = []
    if len(cols) >= 2:
        # Use PCA for 2D viz when more than 2 cols, else direct
        if len(cols) > 2:
            pca = PCA(n_components=2).fit(X)
            proj = pca.transform(X)
            xtitle, ytitle = "PC1", "PC2"
        else:
            proj = X
            xtitle, ytitle = cols[0], cols[1]
        traces = []
        for c in range(k):
            mask = labels == c
            traces.append(scatter_trace(
                proj[mask, 0], proj[mask, 1],
                name=f"cluster {c}",
                row_ids=[str(row_ids[i]) for i in np.where(mask)[0]],
            ))
        charts.append(ChartSpec(
            id=str(uuid.uuid4()), title=f"K-means (k={k})", kind="scatter",
            data=traces,
            layout={"xaxis": {"title": xtitle}, "yaxis": {"title": ytitle}},
            row_ids=[str(i) for i in row_ids],
        ))

    summary = f"K-means with k={k} on {len(cols)} variables. Inertia={fmt(km.inertia_)}."
    return make_result(req, [cluster_table, centroids_table], charts, summary)


def run_hclust(req: AnalysisRequest) -> AnalysisResult:
    df = payload_to_df(req.dataset)
    cols = req.params.get("columns") or numeric_columns(df)
    k = int(req.params.get("k", 3))
    method = req.params.get("method", "ward")
    scale = bool(req.params.get("scale", True))
    require_columns(df, cols)
    if len(cols) < 2:
        raise ValueError("Hierarchical clustering needs at least 2 numeric columns.")

    X, row_ids, sub = _numeric_matrix(df, cols, scale=scale)
    Z = linkage(X, method=method)
    labels = fcluster(Z, t=k, criterion="maxclust")

    table = TableSpec(
        id=str(uuid.uuid4()), title="Cluster sizes",
        columns=["cluster", "n"],
        rows=[[int(c), int((labels == c).sum())] for c in sorted(np.unique(labels))],
    )
    charts: list[ChartSpec] = []
    if len(cols) >= 2:
        if len(cols) > 2:
            proj = PCA(n_components=2).fit_transform(X)
            xtitle, ytitle = "PC1", "PC2"
        else:
            proj = X
            xtitle, ytitle = cols[0], cols[1]
        traces = []
        for c in sorted(np.unique(labels)):
            mask = labels == c
            traces.append(scatter_trace(
                proj[mask, 0], proj[mask, 1],
                name=f"cluster {int(c)}",
                row_ids=[str(row_ids[i]) for i in np.where(mask)[0]],
            ))
        charts.append(ChartSpec(
            id=str(uuid.uuid4()), title=f"Hierarchical clustering (k={k}, {method})", kind="scatter",
            data=traces,
            layout={"xaxis": {"title": xtitle}, "yaxis": {"title": ytitle}},
            row_ids=[str(i) for i in row_ids],
        ))
    return make_result(req, [table], charts, f"Hierarchical clustering (method={method}, k={k}).")
