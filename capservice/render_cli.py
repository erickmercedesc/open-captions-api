from __future__ import annotations

import argparse
from pathlib import Path

from capservice.captions import render_captions


def main() -> None:
    parser = argparse.ArgumentParser(prog="capservice-render")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--template", required=True)
    parser.add_argument("--language", default="")
    parser.add_argument("--model-size", required=True)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--default-template", required=True)
    args = parser.parse_args()
    render_captions(
        Path(args.input),
        Path(args.output),
        template=args.template,
        language=args.language or None,
        model_size=args.model_size,
        backend=args.backend,
        default_template=args.default_template,
    )


if __name__ == "__main__":
    main()
