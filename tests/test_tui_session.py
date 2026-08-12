from __future__ import annotations

import json
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl

import httpx
import pytest

from saizeriya.menu import MenuItem
from saizeriya.tui import session as session_module
from saizeriya.tui.session import (
    MAX_ITEM_COUNT,
    CartLimitError,
    ItemUnavailableError,
    OrderSession,
    UnavailableLinesError,
)

if TYPE_CHECKING:
    from pathlib import Path

QR_URL = "http://example.com/saizeriya3/qr"
LANDING_URL = "http://example.com/saizeriya3/index.php"

SOLD_OUT_CODE = "9999"
MISSING_CODE = "8888"

TOP_PAGE = """
<!doctype html><html><body>
<form id="frm_ctrl" class="top-page" action="./?id0">
  <input id="shop-id" value="42">
  <input id="table-no" value="7">
</form>
<div id="number">2 名様</div>
</body></html>
"""

NUMBER_PAGE = """
<!doctype html><html><body>
<form id="frm_ctrl" class="number-page" action="./?id1">
  <input id="shop-id" value="42"><input id="table-no" value="7">
  <input name="token" value="TKN1"><input id="session-id" value="SID1">
</form>
</body></html>
"""

MENU_PAGE = """
<!doctype html><html><body>
<form id="frm_ctrl" class="menu-page" action="./?id2">
  <input id="shop-id" value="42"><input id="table-no" value="7">
  <input id="number" value="2">
  <input name="token" value="TKN2"><input id="session-id" value="SID2">
</form>
</body></html>
"""

MAIN_PAGE = MENU_PAGE.replace("menu-page", "main-page")

ACCOUNT_PAGE = """
<!doctype html><html><body>
<form id="frm_ctrl" class="account-page" action="./?id4">
  <input id="shop-id" value="42"><input id="table-no" value="7">
  <input name="token" value="TKN4">
</form>
<div id="body-section">
  <div class="list-base"><table><tbody>
    <tr><td>TestDish</td><td>2</td><td>700</td></tr>
  </tbody></table></div>
  <div class="amount"><div class="count"><span>2</span></div><div class="amount"><span>700</span></div></div>
</div>
</body></html>
"""

RECEIPT_PAGE = """
<!doctype html><html><body>
<form id="frm_ctrl" class="receipt-page" action="./?id5">
  <input id="shop-id" value="42"><input id="table-no" value="7">
</form>
<div class="receipt-page"><div class="barcode">
  <img src="data:image/png;base64,AAAA"><p>4200 0700 1234</p>
</div></div>
</body></html>
"""


def _item_response(code: str) -> httpx.Response:
    if code == MISSING_CODE:
        return httpx.Response(200, json={"result": "NG"})
    return httpx.Response(
        200,
        json={
            "result": "OK",
            "alcohol_check": 0,
            "item_data": {
                "id": code,
                "name": f"Dish{code}",
                "price": 350,
                "state": 0 if code == SOLD_OUT_CODE else 1,
            },
        },
    )


PAGE_BY_PROC = {
    "number": NUMBER_PAGE,
    "account": ACCOUNT_PAGE,
    "receipt": RECEIPT_PAGE,
    "main": MAIN_PAGE,
}


def make_transport() -> tuple[httpx.MockTransport, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        url = str(request.url)
        body = dict(parse_qsl(request.content.decode("utf-8"))) if request.content else {}

        if url == QR_URL:
            return httpx.Response(302, headers={"location": LANDING_URL})
        if url == LANDING_URL and request.method == "GET":
            return httpx.Response(200, text=TOP_PAGE)
        if url.startswith(LANDING_URL + "?"):
            return httpx.Response(200, text=PAGE_BY_PROC.get(body.get("proc", ""), MENU_PAGE))
        if url.endswith("/src/cmd/get_item.php"):
            return _item_response(body.get("id", ""))
        if url.endswith("/src/cmd/tbl_call.php"):
            return httpx.Response(200, json={"result": "OK"})

        return httpx.Response(404, text=f"unhandled: {request.method} {url}")

    return httpx.MockTransport(handler), seen


@pytest.fixture
def mock_http(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[httpx.Request]:
    monkeypatch.setenv("SAIZERIYA_CLI_HOME", str(tmp_path))
    transport, seen = make_transport()

    def fake_make_http(cookies: list | None = None) -> httpx.Client:
        del cookies
        return httpx.Client(transport=transport, follow_redirects=True)

    monkeypatch.setattr(session_module, "make_http", fake_make_http)
    return seen


def menu_item(code: str, price: int = 350) -> MenuItem:
    return MenuItem(code=code, name=f"Dish{code}", kana=f"Dish{code}", price=price, category="サラダ")


def test_start_reads_the_table_and_saves_a_snapshot(mock_http: list[httpx.Request], tmp_path: Path) -> None:
    del mock_http
    session = OrderSession.start("t1", QR_URL)
    try:
        assert session.state.shop_id == 42
        assert session.state.table_no == 7
        assert json.loads((tmp_path / "sessions.json").read_text(encoding="utf-8"))["t1"]["state"]["tableNo"] == 7
    finally:
        session.close()


def test_lookup_returns_an_official_menu_item(mock_http: list[httpx.Request]) -> None:
    del mock_http
    session = OrderSession.start("t1", QR_URL)
    try:
        item = session.lookup("1202", menu_item("1202"))
        assert item.name == "Dish1202"
        assert item.price == 350
        assert item.source == "official"
        assert "公式確認済み" in item.tags
        assert item.category == "サラダ"
    finally:
        session.close()


def test_lookup_rejects_sold_out_and_unknown_items(mock_http: list[httpx.Request]) -> None:
    del mock_http
    session = OrderSession.start("t1", QR_URL)
    try:
        with pytest.raises(ItemUnavailableError):
            session.lookup(SOLD_OUT_CODE)
        with pytest.raises(ItemUnavailableError):
            session.lookup(MISSING_CODE)
    finally:
        session.close()


def test_cart_merges_by_code_and_enforces_the_limit(mock_http: list[httpx.Request]) -> None:
    del mock_http
    session = OrderSession.start("t1", QR_URL)
    try:
        session.add_to_cart(menu_item("1202"))
        session.add_to_cart(menu_item("1202"))
        session.add_to_cart(menu_item("3201", price=200))

        assert [(line.code, line.count) for line in session.cart] == [("1202", 2), ("3201", 1)]
        assert session.total_count == 3
        assert session.total_price == 350 * 2 + 200

        session.set_count("1202", MAX_ITEM_COUNT)
        with pytest.raises(CartLimitError):
            session.add_to_cart(menu_item("1202"))

        session.set_count("1202", 0)
        assert [line.code for line in session.cart] == ["3201"]
    finally:
        session.close()


def test_submit_pushes_the_cart_and_clears_it(mock_http: list[httpx.Request]) -> None:
    seen = mock_http
    session = OrderSession.start("t1", QR_URL, people_count=2)
    try:
        session.add_to_cart(menu_item("1202"), count=2)
        session.submit_order()

        assert session.cart == []
        assert session.state.cart == []
        bodies = [dict(parse_qsl(r.content.decode())) for r in seen if r.method == "POST" and "?" in str(r.url)]
        assert any(body.get("ctrl") == "add" and body.get("code") == "1202" for body in bodies)
        submitted = [body for body in bodies if body.get("proc") == "order"]
        assert submitted
        assert submitted[-1]["item[id][]"] == "1202"
        assert submitted[-1]["item[count][]"] == "2"
    finally:
        session.close()


def test_submit_drops_items_the_server_no_longer_serves(mock_http: list[httpx.Request]) -> None:
    del mock_http
    session = OrderSession.start("t1", QR_URL, people_count=2)
    try:
        session.add_to_cart(menu_item("1202"))
        session.add_to_cart(menu_item(SOLD_OUT_CODE))

        with pytest.raises(UnavailableLinesError) as excinfo:
            session.submit_order()

        assert [line.code for line in excinfo.value.lines] == [SOLD_OUT_CODE]
        assert [line.code for line in session.cart] == ["1202"]
        # The remaining line is still submittable afterwards.
        session.submit_order()
        assert session.cart == []
    finally:
        session.close()


def test_submit_rejects_an_empty_cart(mock_http: list[httpx.Request]) -> None:
    del mock_http
    session = OrderSession.start("t1", QR_URL)
    try:
        with pytest.raises(ValueError, match="注文かごが空です"):
            session.submit_order()
    finally:
        session.close()


def test_account_and_receipt_are_parsed(mock_http: list[httpx.Request]) -> None:
    del mock_http
    session = OrderSession.start("t1", QR_URL)
    try:
        account = session.get_account()
        assert account.count == 2
        assert account.total == 700
        assert [line.name for line in account.lines] == ["TestDish"]

        _, receipt = session.get_receipt()
        assert receipt.barcode_value == "420007001234"
    finally:
        session.close()


def test_resume_restores_the_pending_cart_without_replaying_it(mock_http: list[httpx.Request]) -> None:
    del mock_http
    session = OrderSession.start("t1", QR_URL)
    session.add_to_cart(menu_item("1202"), count=2)
    session.close()

    resumed = OrderSession.resume("t1")
    try:
        assert [(line.code, line.count) for line in resumed.cart] == [("1202", 2)]
        # The official client starts clean so a submit does not double-add.
        assert resumed.state.cart == []
    finally:
        resumed.close()


def test_resume_reports_unknown_sessions(mock_http: list[httpx.Request]) -> None:
    del mock_http
    with pytest.raises(ValueError, match="セッションが見つかりません"):
        OrderSession.resume("nope")


def test_call_staff_hits_the_call_endpoint(mock_http: list[httpx.Request]) -> None:
    seen = mock_http
    session = OrderSession.start("t1", QR_URL)
    try:
        assert session.call_staff() == {"result": "OK"}
        assert session.call_staff(dessert=True) == {"result": "OK"}
        calls = [r for r in seen if str(r.url).endswith("tbl_call.php")]
        assert len(calls) == 2
        assert dict(parse_qsl(calls[1].content.decode()))["aft"] == "true"
    finally:
        session.close()
