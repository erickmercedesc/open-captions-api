import shutil
from pathlib import Path

import pytest

from capservice.errors import VideoRejected
from capservice.media import probe, validate_output_video, validate_source_video

ffmpeg = shutil.which("ffmpeg")


def _make_clip(path: Path, *, audio: bool, duration: float = 1.0) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s=320x240:d={duration}",
    ]
    if audio:
        command.extend(
            ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}", "-shortest", "-c:a", "aac"]
        )
    command.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)])
    import subprocess

    subprocess.run(command, check=True, capture_output=True)


@pytest.mark.skipif(ffmpeg is None, reason="ffmpeg is required")
def test_rejects_video_without_audio(tmp_path: Path) -> None:
    clip = tmp_path / "silent.mp4"
    _make_clip(clip, audio=False)
    with pytest.raises(VideoRejected, match="audio"):
        validate_source_video(clip, max_bytes=10_000_000, max_duration_seconds=10)


@pytest.mark.skipif(ffmpeg is None, reason="ffmpeg is required")
def test_rejects_long_video(tmp_path: Path) -> None:
    clip = tmp_path / "long.mp4"
    _make_clip(clip, audio=True, duration=2)
    with pytest.raises(VideoRejected, match="duration"):
        validate_source_video(clip, max_bytes=10_000_000, max_duration_seconds=1)


@pytest.mark.skipif(ffmpeg is None, reason="ffmpeg is required")
def test_accepts_short_clip_and_playable_output(tmp_path: Path) -> None:
    clip = tmp_path / "ok.mp4"
    _make_clip(clip, audio=True, duration=1)
    info = validate_source_video(clip, max_bytes=10_000_000, max_duration_seconds=5)
    assert info.has_video
    assert info.has_audio
    assert probe(clip).duration_seconds > 0
    validate_output_video(clip)
