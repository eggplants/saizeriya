"""Exact-budget gacha dialog."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, ClassVar

from textual import work
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DataTable, Input, Label, Static

from saizeriya.gacha import calculate_exact_budget_gacha
from saizeriya.menu import is_alcohol_menu_item

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from saizeriya.gacha import ExactBudgetResult, ExactBudgetSelection
    from saizeriya.menu import MenuItem

DEFAULT_BUDGET = 1000
MAX_BUDGET = 9999


def _draw(candidates: list[MenuItem], budget: int) -> ExactBudgetResult[MenuItem]:
    """Run the draw off the event loop with a concrete item type."""
    return calculate_exact_budget_gacha(candidates, budget)


class GachaScreen(ModalScreen["list[ExactBudgetSelection[MenuItem]] | None"]):
    """Draw a uniformly random combination of items that costs exactly the budget."""

    BINDINGS: ClassVar = [("escape", "dismiss_gacha", "閉じる")]

    def __init__(self, pool: list[MenuItem], budget: int = DEFAULT_BUDGET) -> None:
        """Draw from `pool` with an initial budget of `budget` yen."""
        super().__init__()
        self._pool = pool
        self._budget = budget
        self._results: list[ExactBudgetSelection[MenuItem]] = []

    def compose(self) -> ComposeResult:
        """Build the gacha dialog."""
        with Vertical():
            yield Label("予算ぴったりガチャ", classes="dialog-title")
            with Horizontal(classes="toolbar"):
                yield Input(value=str(self._budget), type="integer", id="gacha-budget")
                yield Checkbox("お酒を除外", id="gacha-no-alcohol")
            yield Static("予算を入れて「もう一度」を押してください。", id="gacha-summary", classes="hint")
            yield DataTable(id="gacha-results", cursor_type="none", zebra_stripes=True)
            with Horizontal(classes="dialog-buttons"):
                yield Button("閉じる", id="gacha-close")
                yield Button("もう一度", id="gacha-run")
                yield Button("カートに追加", variant="primary", id="gacha-add")

    def on_mount(self) -> None:
        """Prepare the result table and run a first draw."""
        table = self.query_one("#gacha-results", DataTable)
        table.add_columns("商品名", "数量", "小計")
        self.run_gacha()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Re-draw when the alcohol filter is toggled."""
        del event
        self.run_gacha()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route the dialog buttons."""
        if event.button.id == "gacha-run":
            self.run_gacha()
        elif event.button.id == "gacha-add":
            self.dismiss(self._results or None)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Re-draw when the budget is confirmed."""
        del event
        self.run_gacha()

    def action_dismiss_gacha(self) -> None:
        """Close the dialog via the escape key."""
        self.dismiss(None)

    @work(exclusive=True)
    async def run_gacha(self) -> None:
        """Draw a combination for the current budget."""
        try:
            budget = int(self.query_one("#gacha-budget", Input).value.strip())
        except ValueError:
            self.notify("予算は数値で入力してください", severity="error")
            return
        if not 0 <= budget <= MAX_BUDGET:
            self.notify(f"予算は 0〜{MAX_BUDGET} 円で入力してください", severity="error")
            return

        exclude_alcohol = self.query_one("#gacha-no-alcohol", Checkbox).value
        candidates = [
            item for item in self._pool if item.price > 0 and not (exclude_alcohol and is_alcohol_menu_item(item))
        ]

        summary = self.query_one("#gacha-summary", Static)
        summary.update("抽選中…")
        result = await asyncio.to_thread(_draw, candidates, budget)
        self._results = list(result.sample or ())

        table = self.query_one("#gacha-results", DataTable)
        table.clear()
        for selection in self._results:
            table.add_row(selection.item.name, str(selection.quantity), f"¥{selection.subtotal:,}")

        if result.count == 0:
            summary.update(f"{budget:,} 円ぴったりの組み合わせはありません。")
        else:
            total = sum(selection.subtotal for selection in self._results)
            summary.update(f"{budget:,} 円ぴったりの組み合わせは {result.count:,} 通り / 今回の合計 ¥{total:,}")
