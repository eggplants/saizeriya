from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest
from textual.widgets import DataTable, Input, TabbedContent

from saizeriya.tui import session as session_module
from saizeriya.tui.app import SaizeriyaApp
from saizeriya.tui.screens.dialogs import ConfirmScreen, PeopleScreen, TextPromptScreen
from saizeriya.tui.screens.gacha import GachaScreen
from saizeriya.tui.screens.order import OrderScreen
from saizeriya.tui.screens.start import StartScreen

from .test_tui_session import QR_URL, make_transport

if TYPE_CHECKING:
    from pathlib import Path

    from textual.pilot import Pilot

    from saizeriya.tui.session import OrderSession

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_http(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SAIZERIYA_CLI_HOME", str(tmp_path))
    transport, _ = make_transport()

    def fake_make_http(cookies: list | None = None) -> httpx.Client:
        del cookies
        return httpx.Client(transport=transport, follow_redirects=True)

    monkeypatch.setattr(session_module, "make_http", fake_make_http)


async def settle(pilot: Pilot, times: int = 12) -> None:
    """Let the message pump and any background workers catch up."""
    for _ in range(times):
        await pilot.pause()


async def switch_tab(pilot: Pilot, tab_id: str) -> None:
    """Click a tab the way a user would, so focus follows the pane."""
    await pilot.click(f"Tab#--content-tab-{tab_id}")
    await settle(pilot, 10)


def start_screen(app: SaizeriyaApp) -> StartScreen:
    """Return the active start screen."""
    screen = app.screen
    assert isinstance(screen, StartScreen)
    return screen


def order_screen(app: SaizeriyaApp) -> OrderScreen:
    """Return the active ordering screen."""
    screen = app.screen
    assert isinstance(screen, OrderScreen)
    return screen


def session_of(app: SaizeriyaApp) -> OrderSession:
    """Return the open session."""
    assert app.session is not None
    return app.session


async def open_session(pilot: Pilot, name: str = "t1") -> None:
    """Walk the start screen: URL → session name → confirm → people count."""
    app = pilot.app
    assert isinstance(app, SaizeriyaApp)
    start_screen(app).action_start_from_url()
    await settle(pilot)

    prompt = app.screen
    assert isinstance(prompt, TextPromptScreen)
    prompt.query_one("#prompt-input", Input).value = QR_URL
    await pilot.press("enter")
    await settle(pilot)

    prompt = app.screen
    assert isinstance(prompt, TextPromptScreen)
    prompt.query_one("#prompt-input", Input).value = name
    await pilot.press("enter")
    await settle(pilot)

    assert isinstance(app.screen, ConfirmScreen)
    await pilot.click("#confirm-people")
    await settle(pilot)

    assert isinstance(app.screen, PeopleScreen)
    await pilot.click("#people-2")
    await settle(pilot)


@pytest.mark.usefixtures("mock_http")
async def test_start_screen_opens_an_ordering_session() -> None:
    app = SaizeriyaApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        assert isinstance(app.screen, StartScreen)

        await open_session(pilot)

        assert isinstance(app.screen, OrderScreen)
        assert app.session is not None
        assert session_of(app).state.table_no == 7
        assert session_of(app).state.people_count == 2
        assert app.sub_title == "Shop 42 / Table 7 / 2 名"


@pytest.mark.usefixtures("mock_http")
async def test_menu_tab_filters_and_adds_items() -> None:
    app = SaizeriyaApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await open_session(pilot)

        menu_table = order_screen(app).query_one("#menu-table", DataTable)
        assert menu_table.row_count > 50

        search = order_screen(app).query_one("#menu-search", Input)
        search.value = "1202"
        await settle(pilot, 5)
        assert menu_table.row_count == 1

        search.value = ""
        await settle(pilot, 5)

        order_screen(app).query_one("#manual-code", Input).value = "1202"
        await pilot.click("#manual-add")
        await settle(pilot)

        assert [(line.code, line.count) for line in session_of(app).cart] == [("1202", 1)]
        assert "1 点" in str(order_screen(app).query_one("#cart-total").render())


@pytest.mark.usefixtures("mock_http")
async def test_gacha_draws_a_combination_and_fills_the_cart() -> None:
    app = SaizeriyaApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await open_session(pilot)

        order_screen(app).action_open_gacha()
        await settle(pilot)

        gacha = app.screen
        assert isinstance(gacha, GachaScreen)
        gacha.query_one("#gacha-budget", Input).value = "500"
        await pilot.click("#gacha-run")
        await settle(pilot, 25)

        results = gacha.query_one("#gacha-results", DataTable)
        assert results.row_count > 0
        assert "500 円ぴったりの組み合わせは" in str(gacha.query_one("#gacha-summary").render())

        await pilot.click("#gacha-add")
        await settle(pilot, 20)

        assert isinstance(app.screen, OrderScreen)
        assert session_of(app).cart
        assert session_of(app).total_price == 500


@pytest.mark.usefixtures("mock_http")
async def test_gacha_reports_an_impossible_budget() -> None:
    app = SaizeriyaApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await open_session(pilot)

        order_screen(app).action_open_gacha()
        await settle(pilot)

        gacha = app.screen
        assert isinstance(gacha, GachaScreen)
        gacha.query_one("#gacha-budget", Input).value = "7"
        await pilot.click("#gacha-run")
        await settle(pilot, 25)

        assert "組み合わせはありません" in str(gacha.query_one("#gacha-summary").render())
        assert gacha.query_one("#gacha-results", DataTable).row_count == 0

        await pilot.click("#gacha-close")
        await settle(pilot)
        assert isinstance(app.screen, OrderScreen)
        assert session_of(app).cart == []


@pytest.mark.usefixtures("mock_http")
async def test_manual_code_must_be_four_digits() -> None:
    app = SaizeriyaApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await open_session(pilot)

        order_screen(app).query_one("#manual-code", Input).value = "12"
        await pilot.click("#manual-add")
        await settle(pilot)

        assert session_of(app).cart == []


@pytest.mark.usefixtures("mock_http")
async def test_cart_quantity_buttons_and_submit() -> None:
    app = SaizeriyaApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await open_session(pilot)

        order_screen(app).query_one("#manual-code", Input).value = "1202"
        await pilot.click("#manual-add")
        await settle(pilot)

        await switch_tab(pilot, "tab-cart")

        cart_table = order_screen(app).query_one("#cart-table", DataTable)
        cart_table.focus()
        cart_table.move_cursor(row=0)
        await pilot.click("#cart-inc")
        await settle(pilot, 8)
        assert session_of(app).cart[0].count == 2

        await pilot.click("#cart-dec")
        await settle(pilot, 8)
        assert session_of(app).cart[0].count == 1

        await pilot.click("#cart-submit")
        await settle(pilot, 25)

        assert session_of(app).cart == []
        assert order_screen(app).query_one(TabbedContent).active == "tab-history"
        assert order_screen(app).query_one("#account-table", DataTable).row_count == 1
        assert "¥700" in str(order_screen(app).query_one("#account-total").render())


@pytest.mark.usefixtures("mock_http")
async def test_receipt_shows_the_barcode() -> None:
    app = SaizeriyaApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await open_session(pilot)

        await switch_tab(pilot, "tab-history")
        await pilot.click("#account-receipt")
        await settle(pilot, 25)

        assert "420007001234" in str(order_screen(app).query_one("#barcode-value").render())


@pytest.mark.usefixtures("mock_http")
async def test_leaving_and_resuming_a_session() -> None:
    app = SaizeriyaApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await open_session(pilot, "resume-me")

        order_screen(app).query_one("#manual-code", Input).value = "1202"
        await pilot.click("#manual-add")
        await settle(pilot)

        order_screen(app).action_back_to_start()
        await settle(pilot)

        assert isinstance(app.screen, StartScreen)
        assert app.session is None
        session_table = start_screen(app).query_one("#session-table", DataTable)
        assert session_table.row_count == 1

        session_table.focus()
        session_table.move_cursor(row=0)
        start_screen(app).action_resume_selected()
        await settle(pilot, 25)

        assert isinstance(app.screen, OrderScreen)
        assert [(line.code, line.count) for line in session_of(app).cart] == [("1202", 1)]


@pytest.mark.usefixtures("mock_http")
async def test_deleting_a_saved_session() -> None:
    app = SaizeriyaApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await open_session(pilot, "delete-me")
        order_screen(app).action_back_to_start()
        await settle(pilot)

        session_table = start_screen(app).query_one("#session-table", DataTable)
        session_table.focus()
        session_table.move_cursor(row=0)
        start_screen(app).action_delete_selected()
        await settle(pilot)

        assert session_table.row_count == 0


@pytest.mark.usefixtures("mock_http")
async def test_calling_staff_does_not_raise() -> None:
    app = SaizeriyaApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        await open_session(pilot)

        await switch_tab(pilot, "tab-call")
        await pilot.click("#call-staff")
        await settle(pilot, 20)
        await pilot.click("#call-dessert")
        await settle(pilot, 20)
