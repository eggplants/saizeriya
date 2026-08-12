"""Textual TUI for `saizeriya`.

Install with the `tui` extra (`pipx install 'saizeriya[tui]'`) and launch it via
`saizeriya tui`. Pass `--serve` to expose the same UI over HTTP through
`textual-serve`.
"""

from __future__ import annotations

import logging
import os
import shlex
import sys

logger = logging.getLogger(__name__)

MISSING_EXTRA_MESSAGE = "TUI を使うには 'tui' エクストラが必要です: pipx install 'saizeriya[tui]'"

DEFAULT_SERVE_HOST = "localhost"
DEFAULT_SERVE_PORT = 8000


def run(session_name: str | None = None) -> None:
    """Run the TUI in the current terminal."""
    from .app import SaizeriyaApp  # noqa: PLC0415

    SaizeriyaApp(session_name=session_name).run()


def _quote(part: str) -> str:
    """Quote one argument for the shell `textual-serve` spawns the app through."""
    # textual-serve runs the command via asyncio.create_subprocess_shell, so it
    # reaches cmd.exe on Windows, where shlex's POSIX single quotes would be
    # literal characters rather than quoting.
    return f'"{part}"' if os.name == "nt" else shlex.quote(part)


def serve_command(session_name: str | None = None) -> str:
    """Build the command `textual-serve` runs to spawn the TUI for a browser session."""
    # In a PyInstaller build sys.executable is the `saizeriya` CLI itself, which
    # has no `-m` switch — spell the sub-command out as a user would type it.
    launch = ["tui"] if getattr(sys, "frozen", False) else ["-m", "saizeriya.tui"]
    parts = [sys.executable, *launch]
    if session_name:
        parts.append(session_name)
    return " ".join(_quote(part) for part in parts)


def serve(
    host: str = DEFAULT_SERVE_HOST,
    port: int = DEFAULT_SERVE_PORT,
    session_name: str | None = None,
) -> None:
    """Serve the TUI over HTTP with `textual-serve`."""
    from textual_serve.server import Server  # noqa: PLC0415

    Server(serve_command(session_name), host=host, port=port, title="サイゼリヤ TUI").serve()


def main(argv: list[str] | None = None) -> None:
    """Entry point used by `python -m saizeriya.tui`."""
    args = sys.argv[1:] if argv is None else argv
    run(args[0] if args else None)


__all__ = [
    "DEFAULT_SERVE_HOST",
    "DEFAULT_SERVE_PORT",
    "MISSING_EXTRA_MESSAGE",
    "main",
    "run",
    "serve",
    "serve_command",
]
