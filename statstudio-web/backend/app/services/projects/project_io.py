"""Project file I/O and reproducible Python script generation."""
from __future__ import annotations
import json
import io
import zipfile

from app.schemas.project import ProjectFile


CURRENT_SCHEMA = "1.0.0"


def export_project_json(project: ProjectFile) -> bytes:
    project.schema_version = CURRENT_SCHEMA
    return project.model_dump_json(indent=2).encode("utf-8")


def export_project_zip(project: ProjectFile) -> bytes:
    """A .statstudio.zip bundle: project.json + reproducibility script + dataset CSVs."""
    project.schema_version = CURRENT_SCHEMA
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("project.json", project.model_dump_json(indent=2))
        z.writestr("reproduce.py", _reproducibility_script(project))
        # also export datasets as CSV for portability
        for ds in project.datasets:
            csv = _payload_to_csv(ds)
            z.writestr(f"datasets/{_safe_name(ds.name)}.csv", csv)
    return buf.getvalue()


def import_project(content: bytes) -> ProjectFile:
    # Detect zip vs json
    if content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            with z.open("project.json") as f:
                data = json.load(f)
    else:
        data = json.loads(content.decode("utf-8"))
    return ProjectFile(**_migrate(data))


def _migrate(data: dict) -> dict:
    v = data.get("schema_version", "0.0.0")
    if v == CURRENT_SCHEMA:
        return data
    # Future migrations live here. For now, accept older flat shape.
    data["schema_version"] = CURRENT_SCHEMA
    return data


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)[:64]


def _payload_to_csv(payload) -> str:
    import pandas as pd
    df = pd.DataFrame(payload.rows)
    if df.empty:
        df = pd.DataFrame(columns=[c.name for c in payload.columns])
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def _reproducibility_script(project: ProjectFile) -> str:
    """Emit a python snippet that, given the dataset CSVs, re-runs the analyses via API."""
    lines = [
        "# StatStudio reproducibility script",
        f"# Project: {project.name}",
        f"# Generated: {project.created_at}",
        "# Run:  python reproduce.py  (requires the StatStudio backend running on http://localhost:8000)",
        "",
        "import json, pathlib, requests",
        "",
        "API = 'http://localhost:8000/api'",
        "",
        "def load_csv(p):",
        "    import pandas as pd",
        "    df = pd.read_csv(p)",
        "    return {",
        "        'name': p.stem,",
        "        'columns': [{'name': c, 'type': 'numeric' if pd.api.types.is_numeric_dtype(df[c]) else 'text'} for c in df.columns],",
        "        'rows': df.to_dict(orient='records'),",
        "        'row_ids': [str(i) for i in range(len(df))],",
        "    }",
        "",
        "datasets = {p.stem: load_csv(p) for p in pathlib.Path('datasets').glob('*.csv')}",
        "",
    ]
    for i, a in enumerate(project.analyses):
        ds_var = _safe_name(a.dataset.name)
        lines.append(f"# Analysis #{i+1}: {a.type}")
        lines.append(
            f"req = {{'type': {a.type!r}, 'dataset': datasets[{ds_var!r}], "
            f"'params': {json.dumps(a.params)}, 'options': {json.dumps(a.options)}}}"
        )
        lines.append("r = requests.post(f'{API}/analyses/run', json=req); r.raise_for_status()")
        lines.append(f"print('=== {a.type} ===')")
        lines.append("print(r.json()['textual_summary'])")
        lines.append("")
    return "\n".join(lines)
