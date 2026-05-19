"""Integration tests via FastAPI TestClient."""
from __future__ import annotations
import os
import pytest
from fastapi.testclient import TestClient

from app.api.app_factory import create_app

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "samples")


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def _upload(client, fname):
    with open(os.path.join(SAMPLES_DIR, fname), "rb") as f:
        return client.post("/api/files/import", files={"file": (fname, f, "text/csv")})


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_import_csv_and_descriptives(client):
    r = _upload(client, "mtcars.csv")
    assert r.status_code == 200, r.text
    ds = r.json()
    assert ds["name"] == "mtcars"
    # run descriptives via API
    body = {"type": "descriptives", "dataset": ds, "params": {"columns": ["mpg", "hp"]}}
    r2 = client.post("/api/analyses/run", json=body)
    assert r2.status_code == 200, r2.text
    assert r2.json()["type"] == "descriptives"


def test_import_tooth_growth_and_anova(client):
    ds = _upload(client, "ToothGrowth.csv").json()
    body = {"type": "anova_one_way", "dataset": ds, "params": {"response": "len", "factor": "dose"}}
    r = client.post("/api/analyses/run", json=body)
    assert r.status_code == 200, r.text
    summary = r.json()["textual_summary"]
    assert "F=" in summary


def test_import_mtcars_and_regression(client):
    ds = _upload(client, "mtcars.csv").json()
    body = {"type": "regression_ols", "dataset": ds,
            "params": {"response": "mpg", "predictors": ["wt", "hp"]}}
    r = client.post("/api/analyses/run", json=body)
    assert r.status_code == 200, r.text


def test_import_airpassengers_forecast(client):
    ds = _upload(client, "AirPassengers.csv").json()
    body = {"type": "timeseries_forecast", "dataset": ds,
            "params": {"value_column": "passengers", "time_column": "month",
                       "horizon": 6, "method": "ets", "period": 12}}
    r = client.post("/api/analyses/run", json=body)
    assert r.status_code == 200, r.text
    assert len(r.json()["statistical_tables"][0]["rows"]) == 6


def test_project_roundtrip(client):
    ds = _upload(client, "iris.csv").json()
    body = {"type": "pca", "dataset": ds,
            "params": {"columns": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
                       "n_components": 2}}
    res = client.post("/api/analyses/run", json=body).json()
    project = {
        "schema_version": "1.0.0",
        "app_version": "0.1.0",
        "name": "test_project",
        "created_at": "2024-01-01T00:00:00Z",
        "datasets": [ds],
        "dataset_meta": [],
        "analyses": [body],
        "results": [res],
        "dashboards": [],
        "history": [],
        "preferences": {},
    }
    # Export json
    r = client.post("/api/projects/export?fmt=json", json=project)
    assert r.status_code == 200
    # Import back
    import io
    content = r.content
    r2 = client.post("/api/projects/import",
                     files={"file": ("project.json", io.BytesIO(content), "application/json")})
    assert r2.status_code == 200, r2.text
    loaded = r2.json()
    assert loaded["name"] == "test_project"
    assert len(loaded["analyses"]) == 1


def test_html_report(client):
    ds = _upload(client, "mtcars.csv").json()
    body = {"type": "descriptives", "dataset": ds, "params": {"columns": ["mpg"]}}
    res = client.post("/api/analyses/run", json=body).json()
    r = client.post("/api/reports/export/html",
                    json={"title": "Test report", "results": [res]})
    assert r.status_code == 200
    assert b"<html" in r.content
