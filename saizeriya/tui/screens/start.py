"""Entry screen: read a QR code, type a URL, or resume a saved session."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar, cast

import httpx
from textual import work
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Static

from saizeriya.sessions import read_sessions, remove_session
from saizeriya.tui.qr import QRDecodeError, read_qr_url
from saizeriya.tui.session import OrderSession

from .dialogs import ConfirmScreen, PeopleScreen, QRFilePickerScreen, TextPromptScreen

if TYPE_CHECKING:
    from pathlib import Path

    from textual.app import ComposeResult

    from saizeriya.tui.app import SaizeriyaApp

SESSION_ERRORS = (httpx.HTTPError, QRDecodeError, ValueError, TypeError, KeyError, OSError)


class StartScreen(Screen[None]):
    """Choose how to open an ordering session."""

    BINDINGS: ClassVar = [
        ("q", "start_from_qr", "QR画像"),
        ("u", "start_from_url", "URL入力"),
        ("r", "resume_selected", "再開"),
        ("d", "delete_selected", "削除"),
        ("ctrl+r", "refresh_sessions", "一覧更新"),
    ]

    def __init__(self, resume: str | None = None) -> None:
        """Optionally resume the saved session called `resume` once mounted."""
        super().__init__()
        self._resume = resume

    @property
    def saizeriya(self) -> SaizeriyaApp:
        """Return the running application, typed."""
        return cast("SaizeriyaApp", self.app)

    def compose(self) -> ComposeResult:
        """Build the start screen."""
        yield Header()
        with Vertical(id="start-body"):
            yield Static("テーブルの QR コードを画像から読み取るか、URL を直接入力してください。", classes="hint")
            with Horizontal(classes="toolbar"):
                yield Button("QR 画像を読み取る", variant="primary", id="start-qr")
                yield Button("URL を入力", id="start-url")
            yield Static("保存済みセッション", classes="section-title")
            yield DataTable(id="session-table", cursor_type="row", zebra_stripes=True)
            with Horizontal(classes="toolbar"):
                yield Button("再開", id="session-resume")
                yield Button("削除", id="session-delete")
        yield Footer()

    def on_mount(self) -> None:
        """Populate the saved-session table and honour a start-up resume."""
        table = self.query_one("#session-table", DataTable)
        table.add_columns("セッション", "テーブル", "人数", "更新")
        self.refresh_sessions()
        if self._resume:
            name, self._resume = self._resume, None
            self.resume_session(name)

    def on_screen_resume(self) -> None:
        """Reload the session list whenever this screen becomes active again."""
        if self.is_mounted and self.query("#session-table"):
            self.refresh_sessions()

    def refresh_sessions(self) -> None:
        """Reload the saved-session table from disk."""
        table = self.query_one("#session-table", DataTable)
        table.clear()
        for name, snapshot in sorted(read_sessions().items(), key=lambda kv: -kv[1].get("updatedAt", 0)):
            state = snapshot.get("state", {})
            updated = datetime.fromtimestamp(
                snapshot.get("updatedAt", 0) / 1000,
                tz=UTC,
            ).astimezone()
            table.add_row(
                name,
                str(state.get("tableNo", "-")),
                str(state.get("peopleCount", "-")),
                updated.strftime("%Y-%m-%d %H:%M"),
                key=name,
            )

    # --- actions ----------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route the toolbar buttons to their actions."""
        actions = {
            "start-qr": self.action_start_from_qr,
            "start-url": self.action_start_from_url,
            "session-resume": self.action_resume_selected,
            "session-delete": self.action_delete_selected,
        }
        action = actions.get(event.button.id or "")
        if action is not None:
            action()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Resume the double-clicked / Enter-selected session."""
        name = event.row_key.value
        if name:
            self.resume_session(name)

    def action_refresh_sessions(self) -> None:
        """Reload the saved-session table."""
        self.refresh_sessions()

    def action_start_from_qr(self) -> None:
        """Start a session from a QR code image on disk."""
        self.start_from_qr()

    def action_start_from_url(self) -> None:
        """Start a session from a manually entered QR URL."""
        self.start_from_url()

    def action_resume_selected(self) -> None:
        """Resume the session highlighted in the table."""
        name = self._selected_session()
        if name is None:
            self.notify("再開するセッションを選んでください", severity="warning")
            return
        self.resume_session(name)

    def action_delete_selected(self) -> None:
        """Delete the session highlighted in the table."""
        name = self._selected_session()
        if name is None:
            self.notify("削除するセッションを選んでください", severity="warning")
            return
        remove_session(name)
        self.refresh_sessions()
        self.notify(f"{name} を削除しました")

    def _selected_session(self) -> str | None:
        table = self.query_one("#session-table", DataTable)
        if not table.row_count:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        return row_key.value

    # --- workers ----------------------------------------------------------

    @work
    async def start_from_qr(self) -> None:
        """Pick an image, decode it and open the session it points at."""
        path: Path | None = await self.app.push_screen_wait(QRFilePickerScreen())
        if path is None:
            return
        try:
            url = await asyncio.to_thread(read_qr_url, path)
        except QRDecodeError as exc:
            self.notify(str(exc), severity="error")
            return
        self.notify(f"QR を読み取りました: {url}")
        await self._open_new_session(url)

    @work
    async def start_from_url(self) -> None:
        """Ask for a QR URL and open the session it points at."""
        url = await self.app.push_screen_wait(
            TextPromptScreen(
                "QR URL を入力",
                placeholder="https://ioes.saizeriya.co.jp/...",
                hint="テーブルの QR コードが指す URL です。",
            ),
        )
        if url:
            await self._open_new_session(url)

    @work
    async def resume_session(self, name: str) -> None:
        """Reopen the saved session called `name`."""
        try:
            session = await asyncio.to_thread(OrderSession.resume, name)
        except SESSION_ERRORS as exc:
            self.notify(f"セッションを再開できませんでした: {exc}", severity="error")
            return
        self.saizeriya.open_session(session)

    async def _open_new_session(self, url: str) -> None:
        default_name = datetime.now(tz=UTC).astimezone().strftime("table-%m%d-%H%M")
        name = await self.app.push_screen_wait(
            TextPromptScreen("セッション名", value=default_name, hint="保存名として使われます。"),
        )
        if not name:
            return

        try:
            session = await asyncio.to_thread(OrderSession.start, name, url)
        except SESSION_ERRORS as exc:
            self.notify(f"セッションを開始できませんでした: {exc}", severity="error")
            return

        if not await self._confirm_table(session):
            await asyncio.to_thread(session.close)
            self.refresh_sessions()
            return

        self.saizeriya.open_session(session)

    async def _confirm_table(self, session: OrderSession) -> bool:
        choice = await self.app.push_screen_wait(ConfirmScreen(session.state))
        if choice is None:
            return False

        people = session.state.people_count
        if choice != "ok" or people <= 0:
            people = await self.app.push_screen_wait(PeopleScreen(people))
        if people is None:
            return False
        # Submitting the count is also what moves the session off the landing page
        # and onto the menu page, where the request token lives.
        try:
            await asyncio.to_thread(session.set_people_count, people)
        except SESSION_ERRORS as exc:
            self.notify(f"人数を設定できませんでした: {exc}", severity="error")
            return False
        return True
