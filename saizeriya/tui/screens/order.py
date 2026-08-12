"""Ordering screen: add items, manage the cart, check the bill, call staff."""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, ClassVar, Literal, cast

import httpx
from textual import work
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from saizeriya.menu import (
    ALL_CATEGORY,
    MenuItem,
    default_menu,
    filter_menu_for_service_period,
    get_menu_service_period,
    matches_menu_search,
)
from saizeriya.tui.session import ItemUnavailableError, UnavailableLinesError

from .gacha import GachaScreen

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from saizeriya.tui.app import SaizeriyaApp
    from saizeriya.tui.session import OrderSession
    from saizeriya.types import AccountSummary, ReceiptSummary

MenuStatus = Literal["unchecked", "loading", "available", "unavailable", "error"]

STATUS_LABELS: dict[MenuStatus, str] = {
    "unchecked": "未確認",
    "loading": "確認中",
    "available": "注文可",
    "unavailable": "注文不可",
    "error": "確認失敗",
}

ORDER_ERRORS = (httpx.HTTPError, ValueError, TypeError, KeyError)

STATUS_COLUMN = "status"

_CODE_PATTERN = re.compile(r"^\d{4}$")


class OrderScreen(Screen[None]):
    """The four-tab ordering UI backed by a live `OrderSession`."""

    BINDINGS: ClassVar = [
        ("f5", "refresh_account", "会計更新"),
        ("ctrl+g", "open_gacha", "ガチャ"),
        ("ctrl+s", "submit_order", "注文送信"),
        ("escape", "back_to_start", "セッション一覧"),
    ]

    def __init__(self, session: OrderSession) -> None:
        """Drive the screen from an already-open `session`."""
        super().__init__()
        self.session = session
        self._statuses: dict[str, MenuStatus] = {}
        self._menu: list[MenuItem] = list(default_menu())
        self._visible: list[MenuItem] = []
        self._account: AccountSummary | None = None
        self._receipt: ReceiptSummary | None = None

    @property
    def saizeriya(self) -> SaizeriyaApp:
        """Return the running application, typed."""
        return cast("SaizeriyaApp", self.app)

    # --- layout -----------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Build the tabbed ordering UI."""
        yield Header()
        with TabbedContent(initial="tab-add"):
            with TabPane("注文追加", id="tab-add"), Vertical(classes="pane"):
                with Horizontal(classes="toolbar"):
                    yield Input(placeholder="メニューを検索", id="menu-search")
                    yield Select(
                        [(ALL_CATEGORY, ALL_CATEGORY)],
                        value=ALL_CATEGORY,
                        allow_blank=False,
                        id="menu-category",
                    )
                    yield Button("ガチャ", id="menu-gacha")
                with Horizontal(classes="toolbar"):
                    yield Input(placeholder="4桁番号", max_length=4, id="manual-code")
                    yield Button("番号で追加", id="manual-add")
                yield DataTable(id="menu-table", cursor_type="row", zebra_stripes=True)
                yield Static("Enter または「番号で追加」でカートに入ります。", classes="hint")

            with TabPane("注文かご", id="tab-cart"), Vertical(classes="pane"):
                yield DataTable(id="cart-table", cursor_type="row", zebra_stripes=True)
                with Horizontal(classes="toolbar"):
                    yield Button("－", id="cart-dec")
                    yield Button("＋", id="cart-inc")
                    yield Button("削除", id="cart-remove")
                    yield Button("空にする", id="cart-clear")
                with Horizontal(classes="footer-bar"):
                    yield Static("", id="cart-total", classes="total")
                    yield Button("注文送信", variant="primary", id="cart-submit")

            with TabPane("履歴・会計", id="tab-history"), Vertical(classes="pane"):
                yield DataTable(id="account-table", cursor_type="row", zebra_stripes=True)
                yield Static("", id="barcode-value")
                with Horizontal(classes="footer-bar"):
                    yield Static("", id="account-total", classes="total")
                    yield Button("更新", id="account-refresh")
                    yield Button("お会計する", variant="primary", id="account-receipt")

            with TabPane("店員呼出", id="tab-call"), Vertical(classes="pane call-pane"):
                yield Button("店員を呼ぶ", variant="primary", id="call-staff")
                yield Button("デザートを持ってきてもらう", id="call-dessert")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the tables and render the initial state."""
        menu_table = self.query_one("#menu-table", DataTable)
        for label, key in (("番号", "code"), ("商品名", "name"), ("価格", "price"), ("状態", STATUS_COLUMN)):
            menu_table.add_column(label, key=key)
        self.query_one("#cart-table", DataTable).add_columns("番号", "商品名", "数量", "小計")
        self.query_one("#account-table", DataTable).add_columns("商品名", "数量", "金額")
        self.refresh_menu()
        self.refresh_cart()
        self.refresh_title()

    # --- rendering --------------------------------------------------------

    def refresh_title(self) -> None:
        """Show the table details in the header."""
        state = self.session.state
        self.app.title = f"サイゼリヤ - {self.session.name}"
        self.app.sub_title = f"Shop {state.shop_id} / Table {state.table_no} / {state.people_count} 名"

    def refresh_menu(self) -> None:
        """Re-apply the search and category filters to the menu table."""
        period = get_menu_service_period()
        available = filter_menu_for_service_period(self._menu, period)

        categories = [ALL_CATEGORY, *dict.fromkeys(item.category for item in available)]
        select = self.query_one("#menu-category", Select)
        options = [(category, category) for category in categories]
        current = select.value if select.value in categories else ALL_CATEGORY
        select.set_options(options)
        select.value = current

        query = self.query_one("#menu-search", Input).value
        self._visible = [
            item for item in available if current in (ALL_CATEGORY, item.category) and matches_menu_search(item, query)
        ]

        table = self.query_one("#menu-table", DataTable)
        table.clear()
        for item in self._visible:
            table.add_row(
                item.code,
                item.name,
                f"¥{item.price:,}",
                STATUS_LABELS[self._statuses.get(item.code, "unchecked")],
                key=item.code,
            )

    def refresh_cart(self) -> None:
        """Redraw the cart table and its total."""
        table = self.query_one("#cart-table", DataTable)
        table.clear()
        for line in self.session.cart:
            table.add_row(line.code, line.name, str(line.count), f"¥{line.subtotal:,}", key=line.code)
        self.query_one("#cart-total", Static).update(
            f"{self.session.total_count} 点 / 合計 ¥{self.session.total_price:,}",
        )

    def refresh_account(self) -> None:
        """Redraw the account table, total and receipt barcode."""
        table = self.query_one("#account-table", DataTable)
        table.clear()
        account = self._account
        if account is not None:
            for line in account.lines:
                table.add_row(line.name, str(line.count), f"¥{line.price:,}")
        total = self.query_one("#account-total", Static)
        if account is None:
            total.update("「更新」で会計を読み込みます")
        else:
            total.update(f"{account.count} 点 / 合計 ¥{account.total:,}")

        barcode = self.query_one("#barcode-value", Static)
        if self._receipt and self._receipt.barcode_value:
            barcode.update(f"{self._receipt.barcode_value}\nこの番号をレジで提示してください。")
        else:
            barcode.update("")

    def _set_status(self, code: str, status: MenuStatus) -> None:
        self._statuses[code] = status
        table = self.query_one("#menu-table", DataTable)
        if any(item.code == code for item in self._visible):
            table.update_cell(code, STATUS_COLUMN, STATUS_LABELS[status])

    def _activate_tab(self, tab_id: str, focus_selector: str) -> None:
        """Switch to `tab_id` and move focus into it.

        Textual re-activates whichever pane owns the focused widget, so a
        programmatic switch has to take the focus along with it.
        """
        self.query_one(TabbedContent).active = tab_id
        self.query_one(focus_selector).focus()

    def _selected_cart_code(self) -> str | None:
        table = self.query_one("#cart-table", DataTable)
        if not table.row_count:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        return row_key.value

    # --- events -----------------------------------------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter the menu as the search box is typed into."""
        if event.input.id == "menu-search":
            self.refresh_menu()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Add an item when a 4-digit code is confirmed."""
        if event.input.id == "manual-code":
            self._add_manual_code()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Filter the menu when the category changes."""
        if event.select.id == "menu-category":
            self.refresh_menu()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Add the highlighted menu row to the cart."""
        if event.data_table.id != "menu-table":
            return
        code = event.row_key.value
        if code:
            self.add_item(code)

    def on_button_pressed(self, event: Button.Pressed) -> None:  # noqa: C901
        """Route every button on the screen."""
        button_id = event.button.id or ""
        if button_id == "menu-gacha":
            self.action_open_gacha()
        elif button_id == "manual-add":
            self._add_manual_code()
        elif button_id == "cart-inc":
            self._step_cart(1)
        elif button_id == "cart-dec":
            self._step_cart(-1)
        elif button_id == "cart-remove":
            self._remove_cart_line()
        elif button_id == "cart-clear":
            self.session.clear_cart()
            self.refresh_cart()
        elif button_id == "cart-submit":
            self.action_submit_order()
        elif button_id == "account-refresh":
            self.action_refresh_account()
        elif button_id == "account-receipt":
            self.settle_receipt()
        elif button_id == "call-staff":
            self.call_staff(dessert=False)
        elif button_id == "call-dessert":
            self.call_staff(dessert=True)

    # --- actions ----------------------------------------------------------

    def action_back_to_start(self) -> None:
        """Close the session and return to the start screen."""
        self.saizeriya.close_session()

    def action_refresh_account(self) -> None:
        """Reload the account summary."""
        self.load_account()

    def action_submit_order(self) -> None:
        """Send the pending cart to the official system."""
        self.submit_order()

    def action_open_gacha(self) -> None:
        """Open the exact-budget gacha dialog."""
        self.open_gacha()

    def _add_manual_code(self) -> None:
        code = self.query_one("#manual-code", Input).value.strip()
        if not _CODE_PATTERN.match(code):
            self.notify("4 桁のメニュー番号を入力してください", severity="error")
            return
        self.add_item(code)

    def _step_cart(self, delta: int) -> None:
        code = self._selected_cart_code()
        if code is None:
            self.notify("カートの行を選んでください", severity="warning")
            return
        line = self.session.find_line(code)
        if line is None:
            return
        try:
            self.session.set_count(code, line.count + delta)
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return
        self.refresh_cart()

    def _remove_cart_line(self) -> None:
        code = self._selected_cart_code()
        if code is None:
            self.notify("カートの行を選んでください", severity="warning")
            return
        self.session.set_count(code, 0)
        self.refresh_cart()

    # --- workers ----------------------------------------------------------

    @work
    async def add_item(self, code: str) -> None:
        """Confirm `code` with the official system and add it to the cart."""
        fallback = next((item for item in self._menu if item.code == code), None)
        self._set_status(code, "loading")
        try:
            item = await asyncio.to_thread(self.session.lookup, code, fallback)
        except ItemUnavailableError as exc:
            self._set_status(code, "unavailable")
            self.notify(str(exc), severity="error")
            return
        except ORDER_ERRORS as exc:
            self._set_status(code, "error")
            self.notify(f"確認に失敗しました: {exc}", severity="error")
            return

        self._upsert_menu_item(item)
        self._set_status(code, "available")
        try:
            self.session.add_to_cart(item)
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return
        self.query_one("#manual-code", Input).value = ""
        self.refresh_cart()
        self.notify(f"{item.name} をカートに入れました")

    @work(exclusive=True)
    async def load_account(self) -> None:
        """Fetch and render the account summary."""
        try:
            self._account = await asyncio.to_thread(self.session.get_account)
        except ORDER_ERRORS as exc:
            self.notify(f"会計を取得できませんでした: {exc}", severity="error")
            return
        self.refresh_account()
        self.notify("注文履歴を更新しました")

    @work(exclusive=True)
    async def settle_receipt(self) -> None:
        """Settle the bill and show the receipt barcode."""
        try:
            account, self._receipt = await asyncio.to_thread(self.session.get_receipt)
        except ORDER_ERRORS as exc:
            self.notify(f"会計できませんでした: {exc}", severity="error")
            return
        # The receipt page does not always repeat the itemised list; keep the last one.
        if account.lines or account.total:
            self._account = account
        self.refresh_account()
        self.notify("会計を確定しました")

    @work(exclusive=True)
    async def submit_order(self) -> None:
        """Push the cart to the official system and refresh the account."""
        if not self.session.cart:
            self.notify("注文かごが空です", severity="warning")
            return
        try:
            await asyncio.to_thread(self.session.submit_order)
        except UnavailableLinesError as exc:
            for line in exc.lines:
                self._set_status(line.code, "unavailable")
            self.refresh_cart()
            self.notify(str(exc), severity="warning")
            return
        except ORDER_ERRORS as exc:
            self.notify(f"注文を送信できませんでした: {exc}", severity="error")
            return
        self.refresh_cart()
        self.refresh_title()
        self._activate_tab("tab-history", "#account-table")
        self.notify("注文を公式システムへ送信しました")
        self.load_account()

    @work(exclusive=True)
    async def call_staff(self, *, dessert: bool) -> None:
        """Call staff, optionally for dessert service."""
        try:
            await asyncio.to_thread(self.session.call_staff, dessert=dessert)
        except ORDER_ERRORS as exc:
            self.notify(f"呼び出しに失敗しました: {exc}", severity="error")
            return
        self.notify("デザート呼出を送信しました" if dessert else "店員呼出を送信しました")

    @work
    async def open_gacha(self) -> None:
        """Run the gacha dialog and add its result to the cart."""
        period = get_menu_service_period()
        pool = [
            item
            for item in filter_menu_for_service_period(self._menu, period)
            if item.price > 0 and self._statuses.get(item.code) != "unavailable"
        ]
        selections = await self.app.push_screen_wait(GachaScreen(pool))
        if not selections:
            return
        try:
            for selection in selections:
                self.session.add_to_cart(selection.item, selection.quantity)
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return
        self.refresh_cart()
        self.notify("ガチャ結果をカートに入れました")

    def _upsert_menu_item(self, item: MenuItem) -> None:
        for index, existing in enumerate(self._menu):
            if existing.code == item.code:
                self._menu[index] = item
                return
        self._menu.append(item)
        self.refresh_menu()
