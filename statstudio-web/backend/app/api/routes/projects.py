from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response

from app.schemas.project import ProjectFile
from app.services.projects.project_io import (
    export_project_json, export_project_zip, import_project,
)

router = APIRouter()


@router.post("/export")
def export_project(project: ProjectFile, fmt: str = "json"):
    if fmt == "zip":
        data = export_project_zip(project)
        filename = f"{project.name or 'project'}.statstudio.zip"
        return Response(
            content=data, media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    data = export_project_json(project)
    return Response(
        content=data, media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{project.name or "project"}.statstudio.json"'},
    )


@router.post("/import", response_model=ProjectFile)
async def import_project_endpoint(file: UploadFile = File(...)):
    content = await file.read()
    try:
        return import_project(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid project file: {e}")
