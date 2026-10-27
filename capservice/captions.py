from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from capservice.errors import PublicError
from capservice.log import get_logger
from capservice.templates import resolve_template

logger = get_logger(__name__)

_LOG_OUTPUT_LIMIT = 8000


def _output_for_log(value: str | bytes | None, *, limit: int = _LOG_OUTPUT_LIMIT) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    text = text.strip()
    if not text:
        return None
    if len(text) > limit:
        return text[-limit:]
    return text


def render_captions(
    input_path: Path,
    output_path: Path,
    *,
    template: str,
    language: str | None,
    model_size: str,
    backend: str,
    default_template: str,
) -> None:
    """Render animated captions using the official pycaps pipeline API.

    Verified against pycaps 0.3.0:
    - TemplateLoader(name).with_input_video(...).load(False)
    - CapsPipelineBuilder.with_output_video / with_whisper_config / should_save_subtitle_data
    - WhisperBackend.OPENAI | WhisperBackend.FASTER
    - CapsPipeline.run()
    """
    from pycaps import TemplateLoader
    from pycaps.template import BuiltinTemplate, TemplateService
    from pycaps.transcriber import WhisperBackend

    chosen = resolve_template(template, default_template)
    if not TemplateService().is_valid_builtin_template(chosen):
        raise PublicError("Unknown template.")

    if output_path.exists():
        output_path.unlink()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        backend_enum = WhisperBackend(backend)
    except ValueError as exc:
        raise PublicError("Caption generation is not configured correctly.") from exc

    logger.info("pycaps_start", template=chosen, whisper_backend=backend, model=model_size)
    builder = TemplateLoader(BuiltinTemplate(chosen)).with_input_video(str(input_path)).load(False)
    builder.with_output_video(str(output_path))
    builder.should_save_subtitle_data(False)
    builder.with_whisper_config(
        language=language or None,
        model_size=model_size,
        backend=backend_enum,
    )
    pipeline = builder.build()
    pipeline.run()
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise PublicError("Caption generation failed.")
    logger.info("pycaps_done", template=chosen)


def render_captions_isolated(
    input_path: Path,
    output_path: Path,
    *,
    template: str,
    language: str | None,
    model_size: str,
    backend: str,
    default_template: str,
    timeout_seconds: float,
) -> None:
    command = [
        sys.executable,
        "-m",
        "capservice.render_cli",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--template",
        template,
        "--model-size",
        model_size,
        "--backend",
        backend,
        "--default-template",
        default_template,
    ]
    if language:
        command.extend(["--language", language])
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        logger.warning(
            "pycaps_subprocess_timeout",
            stdout=_output_for_log(exc.stdout),
            stderr=_output_for_log(exc.stderr),
        )
        raise PublicError("Processing timed out.") from exc
    if completed.returncode != 0:
        logger.warning(
            "pycaps_subprocess_failed",
            returncode=completed.returncode,
            stdout=_output_for_log(completed.stdout),
            stderr=_output_for_log(completed.stderr),
        )
        raise PublicError("Caption generation failed.")
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise PublicError("Caption generation failed.")
