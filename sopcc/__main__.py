"""Command-line entry point: ``python -m sopcc [file.sopcc]``."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sopcc",
        description="View Softing dataFEED OPC Suite project files (.sopcc).",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Optional .sopcc file to open on startup.",
    )
    args = parser.parse_args(argv)

    try:
        from .gui.app import main as gui_main
    except ImportError as exc:  # pragma: no cover - depends on environment
        print(
            "The GUI requires Tkinter, which is not available in this Python "
            f"installation ({exc}).\nInstall it with: brew install python-tk",
            file=sys.stderr,
        )
        return 1

    gui_main(args.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
