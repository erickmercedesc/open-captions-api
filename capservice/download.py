from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

from capservice.errors import SsrfError, VideoRejected
from capservice.ssrf import validate_public_https_url

_MAX_REDIRECTS = 5
_CHUNK_SIZE = 64 * 1024


def download_video(
    url: str,
    destination: Path,
    *,
    max_bytes: int,
    timeout_seconds: float,
) -> None:
    current = validate_public_https_url(url)
    destination.parent.mkdir(parents=True, exist_ok=True)

    timeout = httpx.Timeout(timeout_seconds)
    with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        for _ in range(_MAX_REDIRECTS + 1):
            validate_public_https_url(current)
            try:
                with client.stream("GET", current) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise VideoRejected("The video could not be downloaded.")
                        current = _absolute_redirect(current, location)
                        continue
                    if response.status_code >= 400:
                        raise VideoRejected("The video could not be downloaded.")
                    _write_limited(response, destination, max_bytes=max_bytes)
                    return
            except httpx.HTTPError as exc:
                raise VideoRejected("The video could not be downloaded.") from exc
    raise VideoRejected("The video could not be downloaded.")


def _absolute_redirect(current: str, location: str) -> str:
    next_url = urljoin(current, location)
    parsed = urlparse(next_url)
    if parsed.scheme != "https":
        raise SsrfError("Only HTTPS URLs are allowed.")
    return validate_public_https_url(next_url)


def _write_limited(response: httpx.Response, destination: Path, *, max_bytes: int) -> None:
    content_length = response.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise VideoRejected("The video exceeds the maximum allowed size.")
        except ValueError:
            pass

    written = 0
    try:
        with destination.open("wb") as handle:
            for chunk in response.iter_bytes(_CHUNK_SIZE):
                if not chunk:
                    continue
                written += len(chunk)
                if written > max_bytes:
                    raise VideoRejected("The video exceeds the maximum allowed size.")
                handle.write(chunk)
    except Exception:
        if destination.exists():
            destination.unlink(missing_ok=True)
        raise

    if written == 0:
        destination.unlink(missing_ok=True)
        raise VideoRejected("The video could not be downloaded.")
