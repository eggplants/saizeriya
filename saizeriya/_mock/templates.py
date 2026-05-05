"""HTML templates for the Saizeriya mock server using tdom t-strings."""

from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from tdom import Markup, html
from tdom.template_utils import template_from_parts

if TYPE_CHECKING:
    from string.templatelib import Template


@dataclass
class RenderContext:
    """Common shell parameters injected into every page."""

    page: str
    next_id: str
    shop_id: int
    table_no: int
    session_id: str
    people_count: int
    token: str


@dataclass
class OrderDisplayLine:
    """A display-ready order line for tables and amount summaries."""

    id: str
    name: str
    count: int
    price: int
    mod_id: str
    mod_count: int
    reorder: int


@dataclass
class CartLine:
    """A raw cart entry matching the hidden form fields sent with orders."""

    id: str
    count: int
    reorder: int
    mod_id: str
    mod_count: int | str


_PLACEHOLDER = "\x00"


def t_dedent(template: Template) -> Template:
    """Dedent and strip a multi-line t-string's static string parts.

    Equivalent to applying textwrap.dedent().strip() to the string portions
    while leaving all interpolated values intact.
    """
    joined = _PLACEHOLDER.join(template.strings)
    processed = textwrap.dedent(joined).strip()
    new_strings = processed.split(_PLACEHOLDER)
    return template_from_parts(new_strings, list(template.interpolations))


_STATIC_DIR = Path(__file__).parent / "static"
_CSS = (_STATIC_DIR / "style.css").read_text(encoding="utf-8")
_CLIENT_SCRIPT_RAW = (_STATIC_DIR / "client.js").read_text(encoding="utf-8")
_DASHBOARD_CSS = (_STATIC_DIR / "dashboard.css").read_text(encoding="utf-8")


def _client_script(page: str) -> str:
    return _CLIENT_SCRIPT_RAW.replace("'%%PAGE%%'", json.dumps(page))


_SELECTED_BY_PAGE: dict[str, str] = {
    "account": "do-account",
    "call": "after-call",
    "history": "order-history",
    "main": "order-list",
    "menu": "order-add",
    "top": "order-add",
}

_DISABLED_BY_PAGE: dict[str, frozenset[str]] = {
    "account": frozenset({"do-account"}),
    "call": frozenset({"after-call"}),
    "main": frozenset({"order-add", "do-account"}),
    "top": frozenset({"order-list"}),
    "menu": frozenset({"order-add"}),
    "number": frozenset({"order-add", "order-list", "order-history", "after-call", "do-account"}),
    "receipt": frozenset({"order-add", "order-list", "order-history", "after-call", "do-account"}),
}

_FOOTER_TABS = [
    ("order-add", "menu", "注文<br />追加"),
    ("order-list", "main", "注文<br />かご"),
    ("order-history", "history", "注文<br />履歴"),
    ("after-call", "call", "店員<br />呼出"),
    ("do-account", "account", "会計<br />する"),
]


def _tab_class(page: str, tab_id: str) -> str:
    parts = []
    if tab_id in _DISABLED_BY_PAGE.get(page, frozenset()):
        parts.append("disabled")
    if _SELECTED_BY_PAGE.get(page) == tab_id:
        parts.append("selected")
    return " ".join(parts)


def _footer(page: str) -> str:
    def _li(tid: str, proc: str, label: str) -> str:
        cls = _tab_class(page, tid)
        is_disabled = "disabled" in cls.split()
        inner = Markup(label)
        return html(
            t_dedent(t"""
            <li id="{tid}" class="{cls}">
                <button type="submit" name="proc" value="{proc}" disabled={is_disabled}>
                    <p>{inner}</p>
                </button>
            </li>
        """)
        )

    items = Markup("".join(_li(*tab) for tab in _FOOTER_TABS))
    return html(t'<div id="footer"><ul id="menu">{items}</ul></div>')


def _brand_logo(*, compact: bool = False) -> str:
    cls = "brand-logo compact" if compact else "brand-logo"
    src = "./data/img/icon.png" if compact else "./data/img/logo.png"
    return html(t'<img class="{cls}" src="{src}" alt="Mock Order" />')


def _amount_summary(count: int, total: int) -> str:
    formatted = f"{total:,}"
    count_p = html(t'<p class="count"><span>{count}</span>点</p>')
    amount_p = html(t'<p class="amount">合計 <span>{formatted}</span>円 (税込)</p>')
    inner = Markup(count_p + amount_p)
    return html(t'<div class="amount">{inner}</div>')


def _order_list(lines: list[OrderDisplayLine], *, is_history: bool = False) -> str:
    def _row(line: OrderDisplayLine) -> str:
        price_str = f"{line.price:,}"
        if is_history:
            reorder_div = html(t'<div class="reorder red" data-id="{line.id}">再注文</div>')
            return html(
                t"<tr><td>{line.name}</td><td>{line.count}</td><td>{price_str}</td><td>{Markup(reorder_div)}</td></tr>"
            )
        return html(t"<tr><td>{line.name}</td><td>{line.count}</td><td>{price_str}</td></tr>")

    rows = Markup("".join(_row(line) for line in lines))
    return html(t'<div class="list-base"><div class="list"><table><tbody>{rows}</tbody></table></div></div>')


def _shell(ctx: RenderContext, title: str, ctrl: str, body: str) -> str:
    """Wrap page body in the standard shell (head, hidden inputs, footer, JS)."""
    css = Markup(_CSS)
    script = Markup(_client_script(ctx.page))
    footer = Markup(_footer(ctx.page))
    body_html = Markup(body)
    page_class = f"{ctx.page}-page"
    return html(
        t_dedent(t"""
        <!doctype html>
        <html lang="ja">
        <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width" />
        <meta name="color-scheme" content="light" />
        <meta name="robots" content="noindex,nofollow" />
        <title>Mock Order</title>
        <style>{css}</style>
        </head>
        <body>
        <div class="off-canvas-wrap">
        <div class="inner-wrap portrait">
        <form id="frm_ctrl" class="{page_class}" action="./?{ctx.next_id}" method="post">
        <input type="hidden" id="proc" name="proc" value="{ctx.page}" />
        <input type="hidden" id="ctrl" name="ctrl" value="{ctrl}" />
        <input type="hidden" id="sub_ctrl" name="sub_ctrl" value="" />
        <input type="hidden" id="cur_lang" name="cur_lang" value="1" />
        <input type="hidden" id="message" name="message" value="" />
        <input type="hidden" id="shop-id" value="{ctx.shop_id}" />
        <input type="hidden" id="table-no" value="{ctx.table_no}" />
        <input type="hidden" id="session-id" value="{ctx.session_id}" />
        <input type="hidden" id="number" name="number" value="{ctx.people_count}" />
        <input type="hidden" id="token" name="token" value="{ctx.token}" />
        <div id="header" class="float-clear"><h1>{title}</h1></div>
        {body_html}
        {footer}
        </form>
        </div>
        </div>
        <script>{script}</script>
        </body>
        </html>
    """)
    )


def render_top_page(ctx: RenderContext) -> str:
    """Render the top/landing page."""
    logo = Markup(_brand_logo())
    people = ctx.people_count
    body = html(
        t_dedent(t"""
        <div id="body-section">
            <div class="logo">{logo}</div>
            <div id="number" class="btn text">{people}名</div>
            <button type="submit" name="proc" value="number" class="button">人数を変更</button>
            <button type="submit" name="proc" value="menu" class="button">注文を始める</button>
        </div>
    """)
    )
    return _shell(ctx, "人数を確認してください", "", body)


def render_number_page(ctx: RenderContext) -> str:
    """Render the people-count entry page."""
    logo = Markup(_brand_logo(compact=True))
    people = ctx.people_count
    body = html(
        t_dedent(t"""
        <div id="body-section">
            <div class="logo">{logo}</div>
            <div class="number">
                <input id="nox" type="number" value="{people}" min="1" max="99" />
            </div>
            <button type="submit" name="proc" value="menu" class="button">決定</button>
        </div>
    """)
    )
    return _shell(ctx, "人数を入力してください", "", body)


def render_menu_page(ctx: RenderContext) -> str:
    """Render the item-code tenkey entry page."""
    logo = Markup(_brand_logo(compact=True))
    body = html(
        t_dedent(t"""
        <input type="hidden" id="drinkbar-cnt" name="drinkbar-cnt" value="0" />
        <input type="hidden" id="alcohol-cnt" name="alcohol-cnt" value="0" />
        <input type="hidden" id="ord-drkbar-cnt" name="ord-drkbar-cnt" value="0" />
        <input type="hidden" id="is_reorder" name="is_reorder" value="0" />
        <input type="hidden" id="order-time" name="order-time" value="" />
        <div id="body-section" class="base">
            <div class="menu">
                <div class="command">
                    <div class="name">&nbsp;</div>
                    <div id="order" class="btn red">注文</div>
                </div>
                <div class="logo">{logo}</div>
                <div class="code"><p id="enter">&nbsp;</p></div>
                <div class="tenkey"><ul>
                    <li class="btn gray" data-val="1">1</li>
                    <li class="btn gray" data-val="2">2</li>
                    <li class="btn gray" data-val="3">3</li>
                    <li class="btn gray" data-val="4">4</li>
                    <li class="btn gray" data-val="5">5</li>
                    <li class="btn gray" data-val="6">6</li>
                    <li class="btn gray" data-val="7">7</li>
                    <li class="btn gray" data-val="8">8</li>
                    <li class="btn gray" data-val="9">9</li>
                    <li class="clear">&nbsp;</li>
                    <li class="btn gray" data-val="0">0</li>
                    <li class="btn green del">削除</li>
                </ul></div>
                <div class="notice-balloon">
                    <div class="balloon-arrow"></div>
                    <div class="msg-base"><span>メニューブックの番号を入力してください。</span></div>
                </div>
            </div>
            <div class="detail">
                <div class="main">
                    <input type="hidden" id="code" name="code" value="" />
                    <dl class="name"><dt>&nbsp;</dt><dd>0円</dd></dl>
                    <ul class="amount">
                        <li class="cmd" id="minus">-</li>
                        <li><input id="amount" name="amount" type="number" value="1" readonly /></li>
                        <li class="cmd" id="plus">+</li>
                    </ul>
                </div>
                <div class="mod" style="display: none;">
                    <input type="hidden" id="mod_code" name="mod_code" value="" />
                    <dl class="name"><dt>&nbsp;</dt><dd></dd></dl>
                    <ul class="amount">
                        <li class="cmd" id="minus">-</li>
                        <li><input id="mod_amount" name="mod_amount" type="number" value="0" readonly /></li>
                        <li class="cmd" id="plus">+</li>
                    </ul>
                    <div id="guide" style="display: none;">
                        <div class="balloon-arrow"></div>
                        <div class="msg-base"><span></span></div>
                    </div>
                </div>
                <div class="command">
                    <button type="submit" name="proc" value="menu" id="back" class="btn gray">もどる</button>
                    <button type="submit" name="proc" value="main" id="decide" class="btn red">確 定</button>
                </div>
            </div>
        </div>
    """)
    )
    return _shell(ctx, "メニューブックから番号を入力してください", "number", body)


def render_main_page(
    ctx: RenderContext,
    display_lines: list[OrderDisplayLine],
    cart: list[CartLine],
) -> str:
    """Render the cart review page with hidden cart fields."""
    order_list = Markup(_order_list(display_lines))
    count = sum(line.count for line in display_lines)
    total = sum(line.price for line in display_lines)
    amount = Markup(_amount_summary(count, total))

    def _hidden_fields(c: CartLine) -> str:
        return "".join(
            [
                html(t'<input type="hidden" name="item[id][]" value="{c.id}" />'),
                html(t'<input type="hidden" name="item[count][]" value="{c.count}" />'),
                html(t'<input type="hidden" name="item[reorder][]" value="{c.reorder}" />'),
                html(t'<input type="hidden" name="item[mod_id][]" value="{c.mod_id}" />'),
                html(t'<input type="hidden" name="item[mod_count][]" value="{c.mod_count}" />'),
            ]
        )

    hidden = Markup("".join(_hidden_fields(c) for c in cart))
    body = html(
        t_dedent(t"""
        <input type="hidden" id="code" name="code" value="" />
        <input type="hidden" id="drinkbar-cnt" name="drinkbar-cnt" value="0" />
        <input type="hidden" id="alcohol-cnt" name="alcohol-cnt" value="0" />
        <input type="hidden" id="ord-drkbar-cnt" name="ord-drkbar-cnt" value="0" />
        <input type="hidden" id="is-first-order" value="YES" />{hidden}
        <div id="body-section">
            {order_list}
            {amount}
            <div class="command">
                <button id="menu" type="submit" name="proc" value="menu" class="btn green">追　加</button>
                <button id="order" type="submit" name="proc" value="order" class="btn red">注文する</button>
            </div>
        </div>
    """)
    )
    return _shell(ctx, "注文内容を確認してください", "remember", body)


def render_call_page(ctx: RenderContext) -> str:
    """Render the post-order staff-call page."""
    shop_id = ctx.shop_id
    table_no = ctx.table_no
    body = html(
        t_dedent(t"""
        <div id="body-section">
            <p class="message">ご注文を受け付けました。</p>
            <div class="call">
                <ul data-shop="{shop_id}" data-tbl="{table_no}">
                    <li id="call-staff" class="btn red">店員を呼ぶ</li>
                    <li id="call-after" class="btn red disabled">デザートを持ってきて</li>
                </ul>
            </div>
            <button type="submit" name="proc" value="menu" class="button">続けて注文</button>
            <button type="submit" name="proc" value="account" class="button">お会計</button>
        </div>
    """)
    )
    return _shell(ctx, "注文を送信しました", "", body)


def render_history_page(ctx: RenderContext, lines: list[OrderDisplayLine]) -> str:
    """Render the order history page."""
    order_list = Markup(_order_list(lines, is_history=True))
    count = sum(line.count for line in lines)
    total = sum(line.price for line in lines)
    amount = Markup(_amount_summary(count, total))
    body = html(
        t_dedent(t"""
        <input type="hidden" id="code" name="code" value="" />
        <div id="body-section">
            {order_list}
            {amount}
            <button type="submit" name="proc" value="menu" class="button">メニューへ</button>
        </div>
    """)
    )
    return _shell(ctx, "注文履歴", "remember", body)


def render_account_page(ctx: RenderContext, lines: list[OrderDisplayLine]) -> str:
    """Render the account summary page."""
    order_list = Markup(_order_list(lines))
    count = sum(line.count for line in lines)
    total = sum(line.price for line in lines)
    amount = Markup(_amount_summary(count, total))
    body = html(
        t_dedent(t"""
        <div id="body-section">
            {order_list}
            {amount}
            <button type="submit" name="proc" value="receipt" class="button">お会計を確定</button>
        </div>
    """)
    )
    return _shell(ctx, "お会計内容", "", body)


_BARCODE_IMG_SRC = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAMoAAAAeCAQAAACd/awtAAAAMUlEQVR42u3PMQEAAAgD"
    "oJvc6FELC4EwSUJCQkJCQkJCQkJCQkJCQkJCQkJCQkKuAX6DAAFs7hJXAAAAAElFTkSuQmCC"
)


def render_receipt_page(ctx: RenderContext, barcode: str) -> str:
    """Render the receipt page with barcode value."""
    logo = Markup(_brand_logo(compact=True))
    table_no = ctx.table_no
    img_src = Markup(_BARCODE_IMG_SRC)
    body = html(
        t_dedent(t"""
        <div id="body-section">
            <p class="table">{table_no}</p>
            <div class="logo">{logo}</div>
            <div class="barcode">
                <img src="{img_src}" alt="" />
                <p>{barcode}</p>
            </div>
            <p class="comment align-justify">この画面をレジで提示ください。</p>
            <p class="comment2">この画面は、お会計後に閉じられます。</p>
        </div>
    """)
    )
    return _shell(ctx, "お会計を確定しました", "", body)


_PAGE_OPTIONS = ["top", "number", "menu", "main", "call", "account", "receipt"]


def render_dashboard(tables: list[dict], menu_items: list[dict]) -> str:
    """Render the admin dashboard page."""

    def _page_option(p: str, current: str) -> str:
        return html(t'<option value="{p}" selected={p == current}>{p}</option>')

    def _cart_entry(item: dict) -> str:
        return html(t"{item['id']} x {item['count']}")

    def _order_entry(i: int, order: list[dict]) -> str:
        inner = Markup(", ".join(_cart_entry(c) for c in order))
        num = i + 1
        return html(t"#{num}: {inner}")

    def _table_section(t: dict) -> str:
        tid = t["id"]
        shop_id = t["shop_id"]
        table_id = t["table_id"]
        people_count = t["people_count"]
        page = t["page"]
        order_started = t["order_started"]
        last_order_closed = t["last_order_closed"]
        midnight_charge = t["midnight_charge"]
        staff_calls = t["staff_call_count"]
        dessert_calls = t["dessert_call_count"]
        qr_url = t["qr_url"]

        options = Markup("".join(_page_option(p, page) for p in _PAGE_OPTIONS))
        cart_html = Markup("<br>".join(_cart_entry(item) for item in t["cart"]) or "empty")
        orders_html = Markup(
            "<br>".join(_order_entry(i, order) for i, order in enumerate(t["submitted_orders"])) or "none"
        )
        return html(
            t_dedent(t"""
            <section class="panel">
                <div class="head"><h2>Table {table_id}</h2><a href="{qr_url}">QR URL</a></div>
                <p class="meta">shop {shop_id} &middot; internal id {tid}</p>
                <form method="post" action="/dashboard/table/{tid}" class="grid">
                    <div>
                        <label for="peopleCount-{tid}">people</label>
                        <input id="peopleCount-{tid}" name="peopleCount" type="number" min="1" value="{people_count}">
                    </div>
                    <div>
                        <label for="page-{tid}">page</label>
                        <select id="page-{tid}" name="page">{options}</select>
                    </div>
                    <div>
                        <input id="orderStarted-{tid}" name="orderStarted" type="checkbox" checked={order_started}>
                        <label for="orderStarted-{tid}">order started</label>
                    </div>
                    <div>
                        <input id="lastOrderClosed-{tid}" name="lastOrderClosed"
                            type="checkbox" checked={last_order_closed}>
                        <label for="lastOrderClosed-{tid}">last order closed</label>
                    </div>
                    <div>
                        <input id="midnightCharge-{tid}" name="midnightCharge"
                            type="checkbox" checked={midnight_charge}>
                        <label for="midnightCharge-{tid}">midnight charge</label>
                    </div>
                    <button type="submit">Update</button>
                </form>
                <div class="split">
                    <div><strong>Cart</strong><p>{cart_html}</p></div>
                    <div><strong>Submitted</strong><p>{orders_html}</p></div>
                    <div><strong>Calls</strong><p>staff {staff_calls} / dessert {dessert_calls}</p></div>
                </div>
                <div class="actions">
                    <form method="post" action="/dashboard/table/{tid}/confirm-order">
                        <button type="submit">Confirm current order</button>
                    </form>
                    <form method="post" action="/dashboard/table/{tid}/clear-cart">
                        <button type="submit">Clear cart</button>
                    </form>
                    <form method="post" action="/dashboard/table/{tid}/reset-calls">
                        <button type="submit">Reset calls</button>
                    </form>
                </div>
            </section>
        """)
        )

    def _menu_row(m: dict) -> str:
        return html(
            t"<tr><td>{m['id']}</td><td>{m['name']}</td><td>{m['price']}</td><td>{m['state']}</td><td>{m['alcohol_check']}</td></tr>"
        )

    sections = Markup("".join(_table_section(t) for t in tables) or '<section class="panel">No tables yet.</section>')
    menu_rows = Markup("".join(_menu_row(m) for m in menu_items))
    css = Markup(_DASHBOARD_CSS)

    return html(
        t_dedent(t"""
        <!doctype html>
        <html lang="ja">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Mock Server Dashboard</title>
            <style>{css}</style>
        </head>
        <body>
            <h1>Mock Server Dashboard</h1>
            <section class="panel">
                <h2>Create table</h2>
                <form method="post" action="/dashboard/tables" class="inline">
                    <div>
                        <label for="create-shopId">shop</label>
                        <input id="create-shopId" name="shopId" type="number" value="525">
                    </div>
                    <div>
                        <label for="create-tableId">table</label>
                        <input id="create-tableId" name="tableId" type="number" value="51">
                    </div>
                    <button type="submit">Create</button>
                </form>
            </section>
            {sections}
            <section class="panel">
                <h2>Menu injection</h2>
                <form method="post" action="/dashboard/menu" class="inline">
                    <div>
                        <label for="menu-id">id</label>
                        <input id="menu-id" name="id" required>
                    </div>
                    <div>
                        <label for="menu-name">name</label>
                        <input id="menu-name" name="name" required>
                    </div>
                    <div>
                        <label for="menu-price">price</label>
                        <input id="menu-price" name="price" type="number" value="0">
                    </div>
                    <div>
                        <label for="menu-state">state</label>
                        <input id="menu-state" name="state" type="number" value="2">
                    </div>
                    <div>
                        <input id="menu-alcohol" name="alcohol_check" type="checkbox">
                        <label for="menu-alcohol">alcohol</label>
                    </div>
                    <button type="submit">Upsert</button>
                </form>
                <table>
                    <thead><tr><th>ID</th><th>Name</th><th>Price</th><th>State</th><th>Alcohol</th></tr></thead>
                    <tbody>{menu_rows}</tbody>
                </table>
            </section>
        </body>
        </html>
    """)
    )
