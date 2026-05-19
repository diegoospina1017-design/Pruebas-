"""Run statistical analyses."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException

from app.schemas.analysis import AnalysisRequest, AnalysisResult
from app.services.analysis import REGISTRY

router = APIRouter()


@router.post("/run", response_model=AnalysisResult)
def run_analysis(req: AnalysisRequest):
    fn = REGISTRY.get(req.type)
    if fn is None:
        raise HTTPException(status_code=400, detail=f"Unknown analysis type: {req.type}")
    try:
        return fn(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing parameter: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")


@router.get("/types")
def list_types():
    return {"types": sorted(REGISTRY.keys())}
