"""FastAPI application factory."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request
import logging

from app.api.routes import datasets, analyses, projects, reports, files, health
from app import __version__

logger = logging.getLogger("statstudio")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")


def create_app() -> FastAPI:
    app = FastAPI(
        title="StatStudio Web API",
        version=__version__,
        description="Statistical analysis backend - Minitab/JMP-style web app.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(files.router, prefix="/api/files", tags=["files"])
    app.include_router(datasets.router, prefix="/api/datasets", tags=["datasets"])
    app.include_router(analyses.router, prefix="/api/analyses", tags=["analyses"])
    app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
    app.include_router(reports.router, prefix="/api/reports", tags=["reports"])

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"error": "validation_error", "details": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": str(exc)},
        )

    return app
