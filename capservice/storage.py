from __future__ import annotations

import secrets
import shutil
from pathlib import Path

from capservice.config import Settings
from capservice.db import Job


def new_output_token() -> str:
    return secrets.token_urlsafe(16)


def parse_output_filename(filename: str) -> tuple[str, str] | None:
    if "/" in filename or "\\" in filename or ".." in filename:
        return None
    if not filename.endswith(".mp4"):
        return None
    stem = filename[:-4]
    if len(stem) < 38 or stem[36] != "-":
        return None
    return stem[:36], stem[37:]


def output_filename(job: Job) -> str:
    if not job.output_token:
        raise FileNotFoundError
    return f"{job.id}-{job.output_token}.mp4"


def output_path(settings: Settings, job: Job) -> Path:
    return settings.outputs_dir / output_filename(job)


def store_output(settings: Settings, job: Job, source: Path) -> Path:
    token = job.output_token or new_output_token()
    job.output_token = token
    destination = settings.outputs_dir / f"{job.id}-{token}.mp4"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    return destination


def public_output_url(settings: Settings, job: Job) -> str:
    return f"{settings.public_base_url}/outputs/{output_filename(job)}"


def delete_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()


def job_tmp_dir(settings: Settings, job_id: str) -> Path:
    path = settings.tmp_dir / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_job_tmp(settings: Settings, job_id: str) -> None:
    path = settings.tmp_dir / job_id
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
