"""Import/export of files (CSV / XLSX)."""
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, HTTPException, Response
from fastapi.responses import Response as FastResponse

from app.services.datasets.import_export import (
    import_csv, import_excel, export_csv, export_excel, preview_csv,
)
from app.schemas.dataset import DatasetPayload

router = APIRouter()

MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB


def _read_upload(file: UploadFile) -> bytes:
    content = file.file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large (>{MAX_FILE_BYTES} bytes).")
    return content


@router.post("/import")
async def import_file(file: UploadFile = File(...)):
    name = (file.filename or "dataset").rsplit(".", 1)[0]
    content = _read_upload(file)
    try:
        if (file.filename or "").lower().endswith(".csv"):
            payload = import_csv(content, name=name)
        else:
            payload = import_excel(content, name=name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")
    return payload.model_dump()


@router.post("/preview")
async def preview_file(file: UploadFile = File(...)):
    content = _read_upload(file)
    if (file.filename or "").lower().endswith(".csv"):
        return preview_csv(content)
    # Treat Excel preview as full import for simplicity (small sheets)
    try:
        payload = import_excel(content, name=(file.filename or "preview"))
        return {
            "columns": [c.model_dump() for c in payload.columns],
            "rows": payload.rows[:50],
            "row_ids": (payload.row_ids or [])[:50],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Preview failed: {e}")


@router.post("/export/csv")
async def export_dataset_csv(payload: DatasetPayload):
    data = export_csv(payload)
    return FastResponse(
        content=data, media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{payload.name}.csv"'},
    )


@router.post("/export/xlsx")
async def export_dataset_xlsx(payload: DatasetPayload):
    data = export_excel(payload)
    return FastResponse(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{payload.name}.xlsx"'},
    )
