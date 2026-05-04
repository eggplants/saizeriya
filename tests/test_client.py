from __future__ import annotations

from urllib.parse import parse_qsl

import httpx
import pytest

from saizeriya import SaizeriyaClient

QR_URL = "http://example.com/saizeriya3/qr"
LANDING_URL = "http://example.com/saizeriya3/index.php"

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
  <input id="shop-id" value="42">
  <input id="table-no" value="7">
  <input name="token" value="TKN1">
  <input id="session-id" value="SID1">
</form>
</body></html>
"""

MENU_PAGE = """
<!doctype html><html><body>
<form id="frm_ctrl" class="menu-page" action="./?id2">
  <input id="shop-id" value="42">
  <input id="table-no" value="7">
  <input id="number" value="2">
  <input name="token" value="TKN2">
  <input id="session-id" value="SID2">
</form>
</body></html>
"""

MAIN_PAGE = """
<!doctype html><html><body>
<form id="frm_ctrl" class="main-page" action="./?id3">
  <input id="shop-id" value="42">
  <input id="table-no" value="7">
  <input id="number" value="2">
  <input name="token" value="TKN3">
  <input id="session-id" value="SID3">
</form>
</body></html>
"""


def _item_response(code: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "result": "OK",
            "item_data": {
                "id": code,
                "name": "TestDish",
                "price": 350,
                "messages": [],
                "mod_id": "",
                "mod_name": "",
                "mod_price": 0,
                "mod_ini_cnt": 0,
                "mod_guid": "",
                "drk_id": "",
                "drk_name": "",
                "drk_price": 0,
                "drk_guid": "",
                "popup": "",
                "notice": "",
                "arc_type": 0,
                "drk_type": 0,
                "main_type": 0,
                "state": 1,
            },
        },
    )


def make_handler() -> tuple[httpx.MockTransport, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        url = str(request.url)

        if url == QR_URL:
            return httpx.Response(302, headers={"location": LANDING_URL})
        if url == LANDING_URL and request.method == "GET":
            return httpx.Response(200, text=TOP_PAGE)

        if url.startswith(LANDING_URL + "?"):
            params = dict(parse_qsl(request.content.decode("utf-8")))
            proc = params.get("proc")
            ctrl = params.get("ctrl", "")
            if proc == "number":
                return httpx.Response(200, text=NUMBER_PAGE)
            if proc == "menu" and ctrl == "number":
                return httpx.Response(200, text=MENU_PAGE)
            if proc == "main":
                return httpx.Response(200, text=MAIN_PAGE)
            return httpx.Response(200, text=MENU_PAGE)

        if url.endswith("/src/cmd/tbl_call.php"):
            return httpx.Response(200, json={"result": "OK"})
        if url.endswith("/src/cmd/get_item.php"):
            params = dict(parse_qsl(request.content.decode("utf-8")))
            return _item_response(params.get("id", ""))

        return httpx.Response(404, text=f"unhandled: {request.method} {url}")

    return httpx.MockTransport(handler), seen


def _new_client(http: httpx.Client | None = None, *, people_count: int | None = 2) -> SaizeriyaClient:
    transport, _ = make_handler()
    return SaizeriyaClient(
        qr_url_source=QR_URL,
        people_count=people_count,
        http=http or httpx.Client(transport=transport, follow_redirects=True),
    )


def test_client_initialises_from_qr_and_calls() -> None:
    transport, _ = make_handler()
    http = httpx.Client(transport=transport, follow_redirects=True)
    with SaizeriyaClient(qr_url_source=QR_URL, people_count=2, http=http) as client:
        state = client.get_state()
        assert state.shop_id == 42
        assert state.table_no == 7
        assert state.people_count == 2
        assert state.page_kind == "menu"
        assert state.token == "TKN2"

        assert client.call() == {"result": "OK"}


def test_client_can_pause_at_top_without_people_count() -> None:
    transport, _ = make_handler()
    http = httpx.Client(transport=transport, follow_redirects=True)
    with SaizeriyaClient(qr_url_source=QR_URL, http=http, people_count=None) as client:
        state = client.get_state()
        assert state.page_kind == "top"
        assert state.people_count == 2


def test_lookup_validates_code() -> None:
    transport, _ = make_handler()
    http = httpx.Client(transport=transport, follow_redirects=True)
    with SaizeriyaClient(qr_url_source=QR_URL, people_count=2, http=http) as client:
        with pytest.raises(ValueError, match="4 digits"):
            client.lookup_item("12")


def test_add_item_appends_to_cart_and_remove_works() -> None:
    transport, _ = make_handler()
    http = httpx.Client(transport=transport, follow_redirects=True)
    with SaizeriyaClient(qr_url_source=QR_URL, people_count=2, http=http) as client:
        client.add_item("1202", count=2)
        client.add_item("3201")
        cart = client.get_state().cart
        assert [c.id for c in cart] == ["1202", "3201"]
        assert cart[0].count == 2
        assert cart[0].name == "TestDish"

        client.remove_cart_item(0)
        assert [c.id for c in client.get_state().cart] == ["3201"]


def test_submit_order_requires_non_empty_cart() -> None:
    transport, _ = make_handler()
    http = httpx.Client(transport=transport, follow_redirects=True)
    with SaizeriyaClient(qr_url_source=QR_URL, people_count=2, http=http) as client:
        with pytest.raises(ValueError, match="empty cart"):
            client.submit_order()
