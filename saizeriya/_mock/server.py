"""Mock HTTP server for Saizeriya's in-store ordering system."""

from __future__ import annotations

import json
import mimetypes
import secrets
import uuid
from copy import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Mount, Route

if TYPE_CHECKING:
    from starlette.datastructures import FormData
    from starlette.requests import Request

from .templates import (
    CartLine,
    OrderDisplayLine,
    RenderContext,
    render_account_page,
    render_call_page,
    render_dashboard,
    render_history_page,
    render_main_page,
    render_menu_page,
    render_number_page,
    render_receipt_page,
    render_top_page,
)

_STATIC_DIR = Path(__file__).parent / "static"
_MENU_JSON = _STATIC_DIR / "dummy_menu_items.json"

Page = Literal["history", "main", "top", "number", "menu", "call", "account", "receipt", "order"]


@dataclass
class MenuItem:
    """A menu item available for ordering."""

    id: str
    name: str
    price: int
    messages: list[str] = field(default_factory=lambda: ["0", "2"])
    mod_id: str = ""
    mod_name: str = ""
    mod_price: int = 0
    mod_ini_cnt: int = 0
    mod_guid: str = ""
    drk_id: str = ""
    drk_name: str = ""
    drk_price: int = 0
    drk_guid: str = ""
    popup: str = ""
    notice: str = ""
    arc_type: int = 0
    drk_type: int = 0
    main_type: int = 0
    state: int = 2
    alcohol_check: int = 0


@dataclass
class TableState:
    """Full runtime state of a single table session."""

    shop_id: int
    table_id: int
    people_count: int
    page: str
    token: str
    session_id: str
    cart: list[CartLine]
    staff_call_count: int
    dessert_call_count: int
    last_order_closed: bool
    midnight_charge: bool
    order_started: bool
    submitted_orders: list[list[CartLine]]
    receipt_shown: bool


def _new_token() -> str:
    return f"{uuid.uuid4()}.{secrets.token_hex(8)}"


def _new_session_id() -> str:
    return uuid.uuid4().hex


def _clone_cart(cart: list[CartLine]) -> list[CartLine]:
    return [copy(line) for line in cart]


def _parse_int(value: object, fallback: int) -> int:
    try:
        return int(str(value or ""))
    except ValueError, TypeError:
        return fallback


def _load_default_menu_items() -> list[MenuItem]:
    if not _MENU_JSON.exists():
        return []
    with _MENU_JSON.open(encoding="utf-8") as f:
        raw: list[dict] = json.load(f)
    items: list[MenuItem] = []
    for entry in raw:
        item_data = entry.get("item_data")
        if item_data:
            d: dict = item_data
            item = MenuItem(
                id=d.get("id", ""),
                name=d.get("name", ""),
                price=d.get("price", 0),
                messages=d.get("messages", ["0", "2"]),
                mod_id=d.get("mod_id", ""),
                mod_name=d.get("mod_name", ""),
                mod_price=d.get("mod_price", 0),
                mod_ini_cnt=d.get("mod_ini_cnt", 0),
                mod_guid=d.get("mod_guid", ""),
                drk_id=d.get("drk_id", ""),
                drk_name=d.get("drk_name", ""),
                drk_price=d.get("drk_price", 0),
                drk_guid=d.get("drk_guid", ""),
                popup=d.get("popup", ""),
                notice=d.get("notice", ""),
                arc_type=d.get("arc_type", 0),
                drk_type=d.get("drk_type", 0),
                main_type=d.get("main_type", 0),
                state=d.get("state", 2),
                alcohol_check=entry.get("alcohol_check") or d.get("alcohol_check", 0),
            )
        elif "code" in entry:
            item = MenuItem(id=entry["code"], name=entry["name"], price=entry.get("price", 0))
        else:
            continue
        if item.id and item.name:
            items.append(item)
    return items


class Table:
    """A single table session managed by the mock server."""

    def __init__(self, server: Server, shop_id: int, table_id: int) -> None:
        """Initialise with default state."""
        self.id: str = str(uuid.uuid4())
        self.server: Server = server
        self.state: TableState = TableState(
            shop_id=shop_id,
            table_id=table_id,
            people_count=2,
            page="top",
            token=_new_token(),
            session_id=_new_session_id(),
            cart=[],
            staff_call_count=0,
            dessert_call_count=0,
            last_order_closed=False,
            midnight_charge=False,
            order_started=False,
            submitted_orders=[],
            receipt_shown=False,
        )

    def qr_url(self, base_path: str = "/saizeriya3") -> str:
        """Return the relative QR redirect URL for this table."""
        return f"{base_path}/qr?table={self.id}"


class Server:
    """Mock Saizeriya ordering server wrapping a Starlette application."""

    def __init__(self, menu_items: list[MenuItem] | None = None) -> None:
        """Initialise with optional custom menu items (defaults to bundled JSON)."""
        self._menu: dict[str, MenuItem] = {}
        self._tables: dict[str, Table] = {}
        self._url_ids: dict[str, Table] = {}
        self.set_menu_items(menu_items if menu_items is not None else _load_default_menu_items())
        self.app: Starlette = self._build_app()

    def set_menu_items(self, items: list[MenuItem]) -> Server:
        """Replace all menu items."""
        self._menu.clear()
        for item in items:
            self._menu[item.id] = item
        return self

    def upsert_menu_item(self, item: MenuItem) -> Server:
        """Insert or update a single menu item."""
        self._menu[item.id] = item
        return self

    def create_table(self, shop_id: int = 525, table_id: int = 51) -> Table:
        """Create and register a new table session."""
        table = Table(self, shop_id, table_id)
        self._tables[table.id] = table
        return table

    def get_table(self, table_id: str) -> Table | None:
        """Look up a table by its UUID."""
        return self._tables.get(table_id)

    def _find_by_shop_table(self, shop_id: object, table_id: object) -> Table | None:
        try:
            sid, tid = int(str(shop_id or "")), int(str(table_id or ""))
        except ValueError, TypeError:
            return None
        return next(
            (t for t in self._tables.values() if t.state.shop_id == sid and t.state.table_id == tid),
            None,
        )

    def _create_url_id(self, table: Table, page: str) -> str:
        url_id = str(uuid.uuid4())
        table.state.page = page
        self._url_ids[url_id] = table
        return url_id

    def _apply_post(self, table: Table, page: str, data: dict[str, str], form: FormData) -> None:
        table.state.page = page
        table.state.token = _new_token()

        if page == "menu" and data.get("ctrl") == "number" and data.get("number"):
            table.state.people_count = _parse_int(data["number"], table.state.people_count)

        if page == "main" and data.get("ctrl") == "add" and data.get("code"):
            table.state.order_started = True
            mod_amt = data.get("mod_amount")
            table.state.cart.append(
                CartLine(
                    id=data["code"],
                    count=_parse_int(data.get("amount"), 1),
                    reorder=0,
                    mod_id=data.get("mod_code", ""),
                    mod_count=_parse_int(mod_amt, 0) if mod_amt else "",
                )
            )

        if page == "order":
            self._confirm_order(table.id, self._cart_from_form(form))

        if page == "receipt":
            table.state.receipt_shown = True

    def _cart_from_form(self, form: FormData) -> list[CartLine]:
        ids = form.getlist("item[id][]")
        counts = form.getlist("item[count][]")
        reorders = form.getlist("item[reorder][]")
        mod_ids = form.getlist("item[mod_id][]")
        mod_counts = form.getlist("item[mod_count][]")
        result = []
        for i, item_id in enumerate(ids):
            mc = mod_counts[i] if i < len(mod_counts) else ""
            result.append(
                CartLine(
                    id=str(item_id),
                    count=_parse_int(counts[i] if i < len(counts) else 1, 1),
                    reorder=1 if (i < len(reorders) and str(reorders[i]) == "1") else 0,
                    mod_id=str(mod_ids[i]) if i < len(mod_ids) else "",
                    mod_count=_parse_int(mc, 0) if mc else "",
                )
            )
        return result

    def _confirm_order(self, table_id: str, order: list[CartLine] | None = None) -> None:
        table = self._tables.get(table_id)
        if not table:
            return
        submitted = order if (order and len(order) > 0) else _clone_cart(table.state.cart)
        if submitted:
            table.state.submitted_orders.append(submitted)
        table.state.cart = []
        table.state.order_started = True
        table.state.page = "call"

    def _build_display_lines(self, items: list[CartLine]) -> list[OrderDisplayLine]:
        lines: dict[str, OrderDisplayLine] = {}
        for item in items:
            menu_item = self._menu.get(item.id)
            modifier = self._menu.get(item.mod_id) if item.mod_id else None
            mod_count = item.mod_count if isinstance(item.mod_count, int) else 0
            unit_price = (menu_item.price if menu_item else 0) + (modifier.price * mod_count if modifier else 0)
            name_parts = [menu_item.name if menu_item else item.id]
            if modifier:
                name_parts.append(modifier.name)
            name = " ".join(name_parts)
            key = f"{item.id}:{item.mod_id}:{mod_count}"
            if key in lines:
                lines[key].count += item.count
                lines[key].price += unit_price * item.count
            else:
                lines[key] = OrderDisplayLine(
                    id=item.id,
                    name=name,
                    count=item.count,
                    price=unit_price * item.count,
                    mod_id=item.mod_id,
                    mod_count=mod_count,
                    reorder=item.reorder,
                )
        return list(lines.values())

    def _receipt_barcode(self, table: Table) -> str:
        control = "".join(str(ord(c) % 10) for c in table.state.session_id)[:6].ljust(6, "0")
        return (str(table.state.shop_id).zfill(3) + str(table.state.table_id).zfill(3) + control)[:12]

    def _make_context(self, table: Table, page: str, next_id: str) -> RenderContext:
        return RenderContext(
            page=page,
            next_id=next_id,
            shop_id=table.state.shop_id,
            table_no=table.state.table_id,
            session_id=table.state.session_id,
            people_count=table.state.people_count,
            token=table.state.token,
        )

    def _render_page(self, table: Table, page: str) -> str:  # noqa: PLR0911
        render_page = "call" if page == "order" else page
        next_id = self._create_url_id(table, render_page)
        ctx = self._make_context(table, render_page, next_id)
        match render_page:
            case "top":
                return render_top_page(ctx)
            case "number":
                return render_number_page(ctx)
            case "menu":
                return render_menu_page(ctx)
            case "main":
                lines = self._build_display_lines(table.state.cart)
                return render_main_page(ctx, lines, _clone_cart(table.state.cart))
            case "call":
                return render_call_page(ctx)
            case "history":
                lines = self._build_display_lines([item for order in table.state.submitted_orders for item in order])
                return render_history_page(ctx, lines)
            case "account":
                lines = self._build_display_lines([item for order in table.state.submitted_orders for item in order])
                return render_account_page(ctx, lines)
            case "receipt":
                return render_receipt_page(ctx, self._receipt_barcode(table))
            case _:
                return render_top_page(ctx)

    def _table_to_dict(self, table: Table) -> dict:
        s = table.state
        return {
            "id": table.id,
            "qr_url": table.qr_url(),
            "shop_id": s.shop_id,
            "table_id": s.table_id,
            "people_count": s.people_count,
            "page": s.page,
            "order_started": s.order_started,
            "last_order_closed": s.last_order_closed,
            "midnight_charge": s.midnight_charge,
            "staff_call_count": s.staff_call_count,
            "dessert_call_count": s.dessert_call_count,
            "cart": [{"id": c.id, "count": c.count} for c in s.cart],
            "submitted_orders": [[{"id": c.id, "count": c.count} for c in order] for order in s.submitted_orders],
        }

    def _build_app(self) -> Starlette:  # noqa: C901,PLR0915
        async def handle_root(_request: Request) -> Response:
            return RedirectResponse(url="/dashboard", status_code=302)

        async def handle_dashboard(_request: Request) -> Response:
            tables = [self._table_to_dict(t) for t in self._tables.values()]
            items = [
                {"id": m.id, "name": m.name, "price": m.price, "state": m.state, "alcohol_check": m.alcohol_check}
                for m in self._menu.values()
            ]
            return HTMLResponse(render_dashboard(tables, items))

        async def handle_create_table(request: Request) -> Response:
            form = await request.form()
            self.create_table(_parse_int(form.get("shopId"), 525), _parse_int(form.get("tableId"), 51))
            return RedirectResponse(url="/dashboard", status_code=303)

        async def handle_update_table(request: Request) -> Response:
            table = self._tables.get(request.path_params["id"])
            if table:
                form = await request.form()
                table.state.people_count = _parse_int(form.get("peopleCount"), table.state.people_count)
                table.state.page = str(form.get("page") or table.state.page)
                table.state.last_order_closed = form.get("lastOrderClosed") == "on"
                table.state.midnight_charge = form.get("midnightCharge") == "on"
                table.state.order_started = form.get("orderStarted") == "on"
            return RedirectResponse(url="/dashboard", status_code=303)

        async def handle_confirm_order(request: Request) -> Response:
            self._confirm_order(request.path_params["id"])
            return RedirectResponse(url="/dashboard", status_code=303)

        async def handle_clear_cart(request: Request) -> Response:
            table = self._tables.get(request.path_params["id"])
            if table:
                table.state.cart = []
            return RedirectResponse(url="/dashboard", status_code=303)

        async def handle_reset_calls(request: Request) -> Response:
            table = self._tables.get(request.path_params["id"])
            if table:
                table.state.staff_call_count = 0
                table.state.dessert_call_count = 0
            return RedirectResponse(url="/dashboard", status_code=303)

        async def handle_upsert_menu(request: Request) -> Response:
            form = await request.form()
            item_id = str(form.get("id") or "").strip()
            name = str(form.get("name") or "").strip()
            if item_id and name:
                self.upsert_menu_item(
                    MenuItem(
                        id=item_id,
                        name=name,
                        price=_parse_int(form.get("price"), 0),
                        state=_parse_int(form.get("state"), 2),
                        alcohol_check=1 if form.get("alcohol_check") == "on" else 0,
                    )
                )
            return RedirectResponse(url="/dashboard", status_code=303)

        async def handle_qr(request: Request) -> Response:
            table_id = request.query_params.get("table")
            table = (self._tables.get(table_id) if table_id else None) or self.create_table(525, 51)
            url_id = self._create_url_id(table, "top")
            base = str(request.url).rsplit("/qr", 1)[0] + "/"
            return RedirectResponse(url=f"{base}?{url_id}", status_code=302)

        async def handle_main(request: Request) -> Response:
            params = request.query_params
            if "SN" in params or "TN" in params:
                shop_id = _parse_int(params.get("SN"), 525)
                table_id = _parse_int(params.get("TB") or params.get("TN"), 51)
                table = self._find_by_shop_table(shop_id, table_id) or self.create_table(shop_id, table_id)
                url_id = self._create_url_id(table, "top")
                base = str(request.url).split("?")[0]
                return RedirectResponse(url=f"{base}?{url_id}", status_code=302)

            url_id = request.url.query
            table = self._url_ids.get(url_id) or self.create_table(525, 51)
            page = table.state.page

            if request.method == "POST":
                form = await request.form()
                data = {k: str(v) for k, v in form.multi_items()}
                page = data.get("proc") or page
                self._apply_post(table, page, data, form)

            return HTMLResponse(self._render_page(table, page))

        async def handle_check_order(request: Request) -> Response:
            form = await request.form()
            table = self._find_by_shop_table(form.get("sid"), form.get("tno") or form.get("tbl"))
            return JSONResponse({"result": "OK" if (table and table.state.order_started) else "NG"})

        async def handle_check_lastorder(request: Request) -> Response:
            form = await request.form()
            table = self._find_by_shop_table(form.get("sid"), form.get("tno") or form.get("tbl"))
            lo = table.state.last_order_closed if table else False
            return JSONResponse({"result": "OK" if lo else "NG", "lastorder": lo})

        async def handle_check_midnight(request: Request) -> Response:
            form = await request.form()
            table = self._find_by_shop_table(form.get("sid"), form.get("tno") or form.get("tbl"))
            return JSONResponse({"result": "OK" if (table and table.state.midnight_charge) else "NG"})

        async def handle_put_alcohol(_request: Request) -> Response:
            return JSONResponse({"result": "OK"})

        async def handle_tbl_call(request: Request) -> Response:
            form = await request.form()
            table = self._find_by_shop_table(form.get("sid"), form.get("tbl"))
            after = str(form.get("aft") or "").lower() == "true"
            if table:
                if after:
                    table.state.dessert_call_count += 1
                else:
                    table.state.staff_call_count += 1
            return JSONResponse({"result": "OK"})

        async def handle_get_item(request: Request) -> Response:
            form = await request.form()
            item_id = str(form.get("id") or "")
            item = self._menu.get(item_id)
            if not item:
                return JSONResponse({"result": "NG"})
            return JSONResponse(
                {
                    "result": "OK",
                    "alcohol_check": item.alcohol_check,
                    "item_data": {
                        "id": item_id,
                        "name": item.name,
                        "price": item.price,
                        "messages": item.messages,
                        "mod_id": item.mod_id,
                        "mod_name": item.mod_name,
                        "mod_price": item.mod_price,
                        "mod_ini_cnt": item.mod_ini_cnt,
                        "mod_guid": item.mod_guid,
                        "drk_id": item.drk_id,
                        "drk_name": item.drk_name,
                        "drk_price": item.drk_price,
                        "drk_guid": item.drk_guid,
                        "popup": item.popup,
                        "notice": item.notice,
                        "arc_type": item.arc_type,
                        "drk_type": item.drk_type,
                        "main_type": item.main_type,
                        "state": item.state,
                    },
                }
            )

        async def handle_data_file(request: Request) -> Response:
            path_str = request.path_params.get("path", "")
            if ".." in path_str:
                return Response("Invalid path", status_code=400)
            file_path = _STATIC_DIR / path_str
            if not file_path.is_file():
                return Response("Not found", status_code=404)
            content_type, _ = mimetypes.guess_type(str(file_path))
            return Response(
                content=file_path.read_bytes(),
                media_type=content_type or "application/octet-stream",
            )

        saizeriya_routes = [
            Route("/qr", endpoint=handle_qr),
            Route("/", endpoint=handle_main, methods=["GET", "POST"]),
            Route("/src/cmd/check_order.php", endpoint=handle_check_order, methods=["POST"]),
            Route("/src/cmd/check_lastorder.php", endpoint=handle_check_lastorder, methods=["POST"]),
            Route("/src/cmd/check_midnight.php", endpoint=handle_check_midnight, methods=["POST"]),
            Route("/src/cmd/put_alcohol.php", endpoint=handle_put_alcohol, methods=["POST"]),
            Route("/src/cmd/tbl_call.php", endpoint=handle_tbl_call, methods=["POST"]),
            Route("/src/cmd/get_item.php", endpoint=handle_get_item, methods=["POST"]),
            Route("/data/{path:path}", endpoint=handle_data_file),
        ]

        return Starlette(
            routes=[
                Route("/", endpoint=handle_root),
                Route("/dashboard", endpoint=handle_dashboard),
                Route("/dashboard/", endpoint=handle_dashboard),
                Route("/dashboard/tables", endpoint=handle_create_table, methods=["POST"]),
                Route("/dashboard/table/{id}", endpoint=handle_update_table, methods=["POST"]),
                Route("/dashboard/table/{id}/confirm-order", endpoint=handle_confirm_order, methods=["POST"]),
                Route("/dashboard/table/{id}/clear-cart", endpoint=handle_clear_cart, methods=["POST"]),
                Route("/dashboard/table/{id}/reset-calls", endpoint=handle_reset_calls, methods=["POST"]),
                Route("/dashboard/menu", endpoint=handle_upsert_menu, methods=["POST"]),
                Mount("/saizeriya2", routes=saizeriya_routes),
                Mount("/saizeriya3", routes=saizeriya_routes),
            ]
        )
