from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from capservice.errors import VideoRejected


@dataclass(frozen=True)
class MediaInfo:
    duration_seconds: float
    has_video: bool
    has_audio: bool
    format_name: str
    size_bytes: int


def require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg and ffprobe must be installed and on PATH.")


def probe(path: Path) -> MediaInfo:
    require_ffmpeg()
    if not path.is_file():
        raise VideoRejected("The video file is missing.")
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise VideoRejected("The file is not a supported video.")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise VideoRejected("The file is not a supported video.") from exc

    streams = payload.get("streams") or []
    fmt = payload.get("format") or {}
    has_video = any(stream.get("codec_type") == "video" for stream in streams)
    has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
    try:
        duration = float(fmt.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    try:
        size_bytes = int(fmt.get("size") or path.stat().st_size)
    except (TypeError, ValueError):
        size_bytes = path.stat().st_size
    return MediaInfo(
        duration_seconds=duration,
        has_video=has_video,
        has_audio=has_audio,
        format_name=str(fmt.get("format_name") or ""),
        size_bytes=size_bytes,
    )


def validate_source_video(path: Path, *, max_bytes: int, max_duration_seconds: float) -> MediaInfo:
    info = probe(path)
    if info.size_bytes > max_bytes:
        raise VideoRejected("The video exceeds the maximum allowed size.")
    if not info.has_video:
        raise VideoRejected("The file is not a supported video.")
    if not info.has_audio:
        raise VideoRejected("The video has no audio track.")
    if info.duration_seconds <= 0:
        raise VideoRejected("The video duration could not be determined.")
    if info.duration_seconds > max_duration_seconds:
        raise VideoRejected("The video exceeds the maximum allowed duration.")
    return info


def validate_output_video(path: Path) -> MediaInfo:
    info = probe(path)
    if not path.is_file() or path.stat().st_size == 0:
        raise VideoRejected("Caption rendering produced an empty file.")
    if not info.has_video:
        raise VideoRejected("The generated file is not a playable video.")
    if info.duration_seconds <= 0:
        raise VideoRejected("The generated file is not a playable video.")
    _decode_first_frame(path)
    return info


def _decode_first_frame(path: Path) -> None:
    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise VideoRejected("The generated file is not a playable video.")
