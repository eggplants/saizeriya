"""Textual application shell for the Saizeriya ordering TUI."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, ClassVar

from textual.app import App

from .screens.order import OrderScreen
from .screens.start import StartScreen

if TYPE_CHECKING:
    from .session import OrderSession


class SaizeriyaApp(App[None]):
    """Order at Saizeriya from the terminal."""

    CSS_PATH = "saizeriya.tcss"
    TITLE = "サイゼリヤ"
    SUB_TITLE = "非公式モバイルオーダー"
    BINDINGS: ClassVar = [("ctrl+q", "quit", "終了")]

    def __init__(self, session_name: str | None = None) -> None:
        """Optionally resume the saved session called `session_name` on start-up."""
        super().__init__()
        self.session: OrderSession | None = None
        self._session_name = session_name

    def on_mount(self) -> None:
        """Show the start screen, resuming a session when one was requested."""
        self.push_screen(StartScreen(resume=self._session_name))

    def open_session(self, session: OrderSession) -> None:
        """Close any previous session and switch to the ordering screen."""
        self._close_session()
        self.session = session
        self.push_screen(OrderScreen(session))

    def close_session(self) -> None:
        """Close the active session and return to the start screen."""
        self._close_session()
        if isinstance(self.screen, OrderScreen):
            self.pop_screen()
        self.title = self.TITLE
        self.sub_title = self.SUB_TITLE

    def _close_session(self) -> None:
        if self.session is not None:
            with contextlib.suppress(OSError):
                self.session.close()
            self.session = None

    def on_unmount(self) -> None:
        """Make sure the HTTP client is closed when the app exits."""
        self._close_session()
