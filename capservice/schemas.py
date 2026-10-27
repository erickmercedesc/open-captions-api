from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from capservice.errors import SsrfError
from capservice.ssrf import validate_public_https_url

JobStatus = Literal["queued", "processing", "completed", "failed"]


class GenerateCaptionsRequest(BaseModel):
    video_url: str
    webhook_url: str
    template: str | None = None

    @field_validator("video_url", "webhook_url")
    @classmethod
    def https_public_url(cls, value: str) -> str:
        try:
            return validate_public_https_url(value)
        except SsrfError as exc:
            raise ValueError(exc.public_message) from exc


class GenerateCaptionsResponse(BaseModel):
    job_id: str
    status: Literal["queued"] = "queued"


class JobView(BaseModel):
    job_id: str
    status: JobStatus
    template: str
    created_at: datetime
    output_url: str | None = None
    error: str | None = None


class WebhookSuccess(BaseModel):
    job_id: str
    status: Literal["completed"] = "completed"
    output_url: str


class WebhookFailure(BaseModel):
    job_id: str
    status: Literal["failed"] = "failed"
    error: str = Field(..., min_length=1)
