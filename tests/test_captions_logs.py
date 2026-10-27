from pathlib import Path
from types import SimpleNamespace

import pytest

from capservice.captions import _output_for_log, render_captions_isolated
from capservice.errors import PublicError


def test_output_for_log_keeps_the_end_of_long_stderr() -> None:
    text = ("a" * 100) + "TRACEBACK"
    clipped = _output_for_log(text, limit=12)
    assert clipped is not None
    assert clipped.endswith("TRACEBACK")
    assert len(clipped) == 12


def test_logs_subprocess_stderr(monkeypatch, tmp_path: Path) -> None:
    recorded: dict[str, object] = {}

    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout="progress line",
            stderr="Traceback (most recent call last):\nRuntimeError: browser not found",
        )

    def fake_warning(event: str, **kwargs: object) -> None:
        recorded["event"] = event
        recorded.update(kwargs)

    monkeypatch.setattr("capservice.captions.subprocess.run", fake_run)
    monkeypatch.setattr("capservice.captions.logger.warning", fake_warning)

    with pytest.raises(PublicError, match="Caption generation failed"):
        render_captions_isolated(
            tmp_path / "in.mp4",
            tmp_path / "out.mp4",
            template="minimalist",
            language="es",
            model_size="base",
            backend="faster",
            default_template="default",
            timeout_seconds=10,
        )

    assert recorded["event"] == "pycaps_subprocess_failed"
    assert recorded["returncode"] == 1
    assert "browser not found" in str(recorded["stderr"])
    assert recorded["stdout"] == "progress line"
