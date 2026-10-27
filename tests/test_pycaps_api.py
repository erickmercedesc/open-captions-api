"""Guard against invented pycaps APIs. Inspects the installed library."""

import inspect

import pytest

pycaps = pytest.importorskip("pycaps")


def test_verified_pipeline_api() -> None:
    from pycaps import CapsPipelineBuilder, DEFAULT_TEMPLATE_NAME, TemplateLoader
    from pycaps.template import BuiltinTemplate, TemplateFactory, TemplateService
    from pycaps.transcriber import WhisperBackend

    assert DEFAULT_TEMPLATE_NAME == "default"
    assert WhisperBackend.FASTER.value == "faster"
    assert WhisperBackend.OPENAI.value == "openai"

    builder_methods = {
        "with_input_video",
        "with_output_video",
        "with_whisper_config",
        "should_save_subtitle_data",
        "build",
    }
    for name in builder_methods:
        assert hasattr(CapsPipelineBuilder, name), name

    signature = inspect.signature(CapsPipelineBuilder.with_whisper_config)
    assert "language" in signature.parameters
    assert "model_size" in signature.parameters
    assert "backend" in signature.parameters

    assert hasattr(TemplateLoader, "with_input_video")
    assert hasattr(TemplateLoader, "load")
    assert hasattr(TemplateFactory, "create")
    assert hasattr(BuiltinTemplate, "get_json_path")

    names = set(TemplateService().list_builtin_templates())
    assert "default" in names
    assert "minimalist" in names
