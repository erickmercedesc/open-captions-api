from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.helpers import ffmpeg_available, integration_enabled, make_spanish_clip

pytestmark = pytest.mark.integration

pycaps = pytest.importorskip("pycaps")


@pytest.mark.skipif(not integration_enabled(), reason="Set RUN_PYCAPS_INTEGRATION=1")
@pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg is required")
@pytest.mark.timeout(600)
def test_spanish_clip_renders_playable_mp4(tmp_path: Path) -> None:
    from capservice.captions import render_captions
    from capservice.media import validate_output_video, validate_source_video

    video = make_spanish_clip(tmp_path / "src")
    validate_source_video(video, max_bytes=20_000_000, max_duration_seconds=30)
    output = tmp_path / "captions.mp4"
    render_captions(
        video,
        output,
        template="minimalist",
        language="es",
        model_size=os.environ.get("WHISPER_MODEL", "tiny"),
        backend=os.environ.get("WHISPER_BACKEND", "faster"),
        default_template="default",
    )
    info = validate_output_video(output)
    assert output.stat().st_size > 0
    assert info.has_video
    assert info.duration_seconds > 0
