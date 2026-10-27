from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def fixture_spanish_clip() -> Path:
    return Path(__file__).parent / "fixtures" / "spanish.mp4"


def make_spanish_clip(directory: Path) -> Path:
    """Return the committed Spanish clip, or generate one with gTTS if missing."""
    fixture = fixture_spanish_clip()
    directory.mkdir(parents=True, exist_ok=True)
    video = directory / "spanish.mp4"
    if fixture.is_file():
        shutil.copyfile(fixture, video)
        return video

    from gtts import gTTS

    speech = directory / "speech.mp3"
    gTTS("Hola, esta es una prueba de subtítulos animados.", lang="es").save(str(speech))
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=720x1280:d=4",
            "-i",
            str(speech),
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(video),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return video


def integration_enabled() -> bool:
    return os.environ.get("RUN_PYCAPS_INTEGRATION") == "1"
