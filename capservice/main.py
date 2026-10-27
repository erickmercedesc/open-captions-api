from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session, sessionmaker

from capservice.auth import require_api_key
from capservice.config import Settings, get_settings
from capservice.db import create_db_engine, session_factory
from capservice.errors import PublicError
from capservice.log import configure_logging, get_logger
from capservice.repository import create_job, get_job
from capservice.schemas import GenerateCaptionsRequest, GenerateCaptionsResponse, JobView
from capservice.storage import output_filename, output_path, parse_output_filename, public_output_url
from capservice.templates import resolve_template

logger = get_logger(__name__)


def _host_only(url: str) -> str:
    return urlparse(url).hostname or "unknown"


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    engine = create_db_engine(settings.db_path)
    app.state.settings = settings
    app.state.session_factory = session_factory(engine)
    logger.info("api_started")
    yield


def get_db(request: Request) -> Session:
    factory: sessionmaker[Session] = request.app.state.session_factory
    session = factory()
    try:
        yield session
    finally:
        session.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="CapService",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    @app.exception_handler(PublicError)
    async def public_error_handler(_request: Request, exc: PublicError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": exc.public_message})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/generate-captions",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=GenerateCaptionsResponse,
        dependencies=[Depends(require_api_key)],
    )
    def generate_captions(
        payload: GenerateCaptionsRequest,
        settings: Annotated[Settings, Depends(get_settings)],
        session: Annotated[Session, Depends(get_db)],
    ) -> GenerateCaptionsResponse:
        template = resolve_template(payload.template, settings.default_template)
        job = create_job(
            session,
            video_url=payload.video_url,
            webhook_url=payload.webhook_url,
            template=template,
        )
        logger.info(
            "job_queued",
            job_id=job.id,
            template=template,
            video_host=_host_only(payload.video_url),
            webhook_host=_host_only(payload.webhook_url),
        )
        return GenerateCaptionsResponse(job_id=job.id, status="queued")

    @app.get(
        "/jobs/{job_id}",
        response_model=JobView,
        dependencies=[Depends(require_api_key)],
    )
    def read_job(
        job_id: str,
        settings: Annotated[Settings, Depends(get_settings)],
        session: Annotated[Session, Depends(get_db)],
    ) -> JobView:
        job = get_job(session, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        output_url = None
        if job.status == "completed" and job.output_token:
            path = output_path(settings, job)
            if path.is_file():
                output_url = public_output_url(settings, job)
        return JobView(
            job_id=job.id,
            status=job.status,  # type: ignore[arg-type]
            template=job.template,
            created_at=job.created_at,
            output_url=output_url,
            error=job.error if job.status == "failed" else None,
        )

    @app.get("/outputs/{filename}")
    def download_output(
        filename: str,
        settings: Annotated[Settings, Depends(get_settings)],
        session: Annotated[Session, Depends(get_db)],
    ) -> FileResponse:
        parsed = parse_output_filename(filename)
        if parsed is None:
            raise HTTPException(status_code=404, detail="Not found.")
        job_id, _token = parsed
        job = get_job(session, job_id)
        if job is None or job.status != "completed" or not job.output_token:
            raise HTTPException(status_code=404, detail="Not found.")
        if filename != output_filename(job):
            raise HTTPException(status_code=404, detail="Not found.")
        path = output_path(settings, job)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Not found.")
        try:
            path.resolve().relative_to(settings.outputs_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=404, detail="Not found.") from None
        return FileResponse(path, media_type="video/mp4", filename=f"{job.id}.mp4")

    return app


app = create_app()
