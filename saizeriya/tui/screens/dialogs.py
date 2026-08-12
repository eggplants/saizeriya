"""Modal dialogs: QR image picker, free-text prompt, confirmation, people count."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from textual.containers import Grid, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Input, Label, Static

from saizeriya.tui.qr import is_image_file

if TYPE_CHECKING:
    from collections.abc import Iterable

    from textual.app import ComposeResult

    from saizeriya.types import ClientState

MAX_PEOPLE_BUTTONS = 8


class ImageDirectoryTree(DirectoryTree):
    """Directory tree that only shows directories and readable image files."""

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """Hide dotfiles and anything that is not a directory or image."""
        return [path for path in paths if not path.name.startswith(".") and (path.is_dir() or is_image_file(path))]


class QRFilePickerScreen(ModalScreen[Path | None]):
    """Pick a local image file that contains the in-store QR code."""

    BINDINGS: ClassVar = [("escape", "dismiss_picker", "閉じる")]

    def __init__(self, start_path: Path | None = None) -> None:
        """Open the picker rooted at `start_path` (defaults to the home directory)."""
        super().__init__()
        self._start_path = start_path or Path.home()

    def compose(self) -> ComposeResult:
        """Build the picker dialog."""
        with Vertical():
            yield Label("QR コード画像を選ぶ", classes="dialog-title")
            yield Static(
                "テーブルの QR コードを撮影・スクリーンショットした画像を選んでください。",
                classes="hint",
            )
            yield Input(placeholder="パスを直接入力して Enter", id="qr-path")
            yield ImageDirectoryTree(self._start_path, id="qr-tree")
            with Horizontal(classes="dialog-buttons"):
                yield Button("閉じる", id="qr-cancel")

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Return the picked file."""
        self.dismiss(event.path)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Return a manually typed path."""
        path = Path(event.value.strip()).expanduser()
        if not path.is_file():
            self.notify(f"ファイルが見つかりません: {path}", severity="error")
            return
        self.dismiss(path)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Close the picker without a selection."""
        if event.button.id == "qr-cancel":
            self.dismiss(None)

    def action_dismiss_picker(self) -> None:
        """Close the picker via the escape key."""
        self.dismiss(None)


class TextPromptScreen(ModalScreen[str | None]):
    """Ask the user for a single line of text."""

    BINDINGS: ClassVar = [("escape", "dismiss_prompt", "閉じる")]

    def __init__(self, title: str, placeholder: str = "", value: str = "", hint: str = "") -> None:
        """Configure the prompt's title, placeholder, initial value and hint."""
        super().__init__()
        self._title = title
        self._placeholder = placeholder
        self._value = value
        self._hint = hint

    def compose(self) -> ComposeResult:
        """Build the prompt dialog."""
        with Vertical():
            yield Label(self._title, classes="dialog-title")
            if self._hint:
                yield Static(self._hint, classes="hint")
            yield Input(value=self._value, placeholder=self._placeholder, id="prompt-input")
            with Horizontal(classes="dialog-buttons"):
                yield Button("キャンセル", id="prompt-cancel")
                yield Button("決定", variant="primary", id="prompt-ok")

    def on_mount(self) -> None:
        """Focus the text field."""
        self.query_one("#prompt-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Accept the typed value."""
        self.dismiss(event.value.strip() or None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Accept or cancel the prompt."""
        if event.button.id == "prompt-ok":
            self.dismiss(self.query_one("#prompt-input", Input).value.strip() or None)
        else:
            self.dismiss(None)

    def action_dismiss_prompt(self) -> None:
        """Cancel the prompt via the escape key."""
        self.dismiss(None)


class ConfirmScreen(ModalScreen[str | None]):
    """Confirm the table read from the QR code before ordering."""

    BINDINGS: ClassVar = [("escape", "dismiss_confirm", "読み直す")]

    def __init__(self, state: ClientState) -> None:
        """Show the table details carried by `state`."""
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        """Build the confirmation dialog."""
        people = self._state.people_count
        suffix = f" / {people} 名様" if people > 0 else ""
        with Vertical():
            yield Label(f"{self._state.table_no} テーブル{suffix}で間違いないですか？", classes="dialog-title")
            yield Static(f"Shop {self._state.shop_id}", classes="hint")
            with Horizontal(classes="dialog-buttons"):
                yield Button("読み直す", id="confirm-cancel")
                if people > 0:
                    yield Button("人数変更", id="confirm-people")
                    yield Button("注文へ進む", variant="primary", id="confirm-ok")
                else:
                    yield Button("次へ", variant="primary", id="confirm-people")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Return the chosen action."""
        actions = {"confirm-ok": "ok", "confirm-people": "people"}
        self.dismiss(actions.get(event.button.id or ""))

    def action_dismiss_confirm(self) -> None:
        """Cancel via the escape key."""
        self.dismiss(None)


class PeopleScreen(ModalScreen[int | None]):
    """Ask how many people are seated at the table."""

    BINDINGS: ClassVar = [("escape", "dismiss_people", "戻る")]

    def __init__(self, current: int = 2) -> None:
        """Pre-fill the input with `current`."""
        super().__init__()
        self._current = current if current > 0 else 2

    def compose(self) -> ComposeResult:
        """Build the people-count dialog."""
        with Vertical():
            yield Label("何名様でご利用ですか？", classes="dialog-title")
            with Grid(id="people-grid"):
                for count in range(1, MAX_PEOPLE_BUTTONS + 1):
                    yield Button(f"{count} 人", id=f"people-{count}")
            yield Input(value=str(self._current), placeholder="9 人以上", type="integer", id="people-input")
            with Horizontal(classes="dialog-buttons"):
                yield Button("戻る", id="people-cancel")
                yield Button("確定", variant="primary", id="people-ok")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle a preset button, the confirm button or cancellation."""
        button_id = event.button.id or ""
        if button_id.startswith("people-") and button_id.removeprefix("people-").isdigit():
            self.dismiss(int(button_id.removeprefix("people-")))
        elif button_id == "people-ok":
            self._submit(self.query_one("#people-input", Input).value)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Confirm the typed count."""
        self._submit(event.value)

    def action_dismiss_people(self) -> None:
        """Cancel via the escape key."""
        self.dismiss(None)

    def _submit(self, raw: str) -> None:
        try:
            count = int(raw.strip())
        except ValueError:
            self.notify("人数は数値で入力してください", severity="error")
            return
        if not 1 <= count <= 99:  # noqa: PLR2004
            self.notify("人数は 1〜99 の範囲で入力してください", severity="error")
            return
        self.dismiss(count)
