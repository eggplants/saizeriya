from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from saizeriya.tui import serve_command

if TYPE_CHECKING:
    from pathlib import Path


def test_serve_command_runs_the_module_when_not_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "executable", "/usr/bin/python3")
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert serve_command() == "/usr/bin/python3 -m saizeriya.tui"


def test_serve_command_appends_the_session_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "executable", "/usr/bin/python3")
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert serve_command("mysession") == "/usr/bin/python3 -m saizeriya.tui mysession"


def test_serve_command_calls_the_cli_when_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    # A PyInstaller binary is the CLI itself: `-m saizeriya.tui` would be parsed
    # as sub-command arguments and fail.
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/opt/saizeriya")

    assert serve_command("mysession") == "/opt/saizeriya tui mysession"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX quoting")
def test_serve_command_quotes_paths_with_spaces(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    binary = tmp_path / "my downloads" / "saizeriya"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(binary))

    assert serve_command() == f"'{binary}' tui"
