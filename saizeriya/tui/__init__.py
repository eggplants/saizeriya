"""Textual TUI for `saizeriya`.

Install with the `tui` extra (`pipx install 'saizeriya[tui]'`) and launch it via
`saizeriya tui`. Pass `--serve` to expose the same UI over HTTP through
`textual-serve`.
"""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)

MISSING_EXTRA_MESSAGE = "TUI を使うには 'tui' エクストラが必要です: pipx install 'saizeriya[tui]'"

DEFAULT_SERVE_HOST = "localhost"
DEFAULT_SERVE_PORT = 8000


def run(session_name: str | None = None) -> None:
    """Run the TUI in the current terminal."""
    from .app import SaizeriyaApp  # noqa: PLC0415

    SaizeriyaApp(session_name=session_name).run()


def serve(
    host: str = DEFAULT_SERVE_HOST,
    port: int = DEFAULT_SERVE_PORT,
    session_name: str | None = None,
) -> None:
    """Serve the TUI over HTTP with `textual-serve`."""
    from textual_serve.server import Server  # noqa: PLC0415

    command = f"{sys.executable} -m saizeriya.tui"
    if session_name:
        command = f"{command} {session_name}"
    Server(command, host=host, port=port, title="サイゼリヤ TUI").serve()


def main(argv: list[str] | None = None) -> None:
    """Entry point used by `python -m saizeriya.tui`."""
    args = sys.argv[1:] if argv is None else argv
    run(args[0] if args else None)


__all__ = ["DEFAULT_SERVE_HOST", "DEFAULT_SERVE_PORT", "MISSING_EXTRA_MESSAGE", "main", "run", "serve"]
