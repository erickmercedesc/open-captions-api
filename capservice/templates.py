from __future__ import annotations

import re

from capservice.errors import PublicError

_TEMPLATE_NAME = re.compile(r"^[a-z0-9-]+$")

# Built-in templates shipped by pycaps 0.3.0. Runtime listing is preferred.
KNOWN_BUILTIN_TEMPLATES = (
    "classic",
    "default",
    "explosive",
    "fast",
    "hype",
    "line-focus",
    "minimalist",
    "model",
    "neo-minimal",
    "retro-gaming",
    "vibrant",
    "word-focus",
)


def list_builtin_templates() -> list[str]:
    try:
        from pycaps.template import TemplateService

        names = TemplateService().list_builtin_templates()
        return sorted(name for name in names if _TEMPLATE_NAME.fullmatch(name))
    except Exception:
        return list(KNOWN_BUILTIN_TEMPLATES)


def resolve_template(name: str | None, default: str) -> str:
    chosen = (name or default).strip().lower()
    if not _TEMPLATE_NAME.fullmatch(chosen):
        raise PublicError("Unknown template.")
    allowed = set(list_builtin_templates())
    if chosen not in allowed:
        raise PublicError("Unknown template.")
    return chosen
