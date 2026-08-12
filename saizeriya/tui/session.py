"""Session object shared by the TUI screens.

Wraps `SaizeriyaClient` with a pending local cart, mirroring `betterzeriya`:
items are checked against the official system as soon as they are picked, but
they are only pushed to the server when the order is actually submitted.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from saizeriya.client import SaizeriyaClient
from saizeriya.menu import MenuItem
from saizeriya.sessions import (
    make_http,
    read_sessions,
    save_session,
    state_from_dict,
)
from saizeriya.types import CartItem

if TYPE_CHECKING:
    import httpx

    from saizeriya.types import AccountSummary, ClientState, ReceiptSummary

MAX_ITEM_COUNT = 99


@dataclass
class CartLine:
    """One pending cart entry, merged by item code."""

    code: str
    name: str
    price: int
    count: int

    @property
    def subtotal(self) -> int:
        """Return price times count."""
        return self.price * self.count


class CartLimitError(ValueError):
    """Raised when a cart line would exceed the per-item maximum."""

    def __init__(self) -> None:
        """Build the error with the user-facing message."""
        super().__init__(f"数量は {MAX_ITEM_COUNT} 点までです")


class ItemUnavailableError(ValueError):
    """Raised when the official system rejects an item code."""

    def __init__(self, code: str) -> None:
        """Build the error for the rejected `code`."""
        super().__init__(f"メニュー番号 {code} は利用できません")
        self.code = code


class UnavailableLinesError(ValueError):
    """Raised when cart lines had to be dropped before submitting."""

    def __init__(self, lines: list[CartLine]) -> None:
        """Build the error for the dropped `lines`."""
        names = "、".join(f"{line.name}({line.code})" for line in lines)
        super().__init__(f"注文できないため取り除きました: {names}")
        self.lines = lines


class OrderSession:
    """A named ordering session: HTTP client, official client and local cart."""

    def __init__(
        self,
        name: str,
        http: httpx.Client,
        client: SaizeriyaClient,
        created_at: int,
        cart: list[CartLine] | None = None,
    ) -> None:
        """Bind an already-open client to a session name."""
        self.name = name
        self.http = http
        self.client = client
        self.created_at = created_at
        self.cart: list[CartLine] = cart or []

    # --- lifecycle --------------------------------------------------------

    @classmethod
    def start(cls, name: str, qr_url: str, people_count: int | None = None) -> OrderSession:
        """Open a brand new session from a QR URL."""
        http = make_http()
        try:
            client = SaizeriyaClient(qr_url_source=qr_url, people_count=people_count, http=http)
        except Exception:
            http.close()
            raise
        session = cls(name=name, http=http, client=client, created_at=int(time.time() * 1000))
        session.save()
        return session

    @classmethod
    def resume(cls, name: str) -> OrderSession:
        """Reopen a previously saved session."""
        snapshot = read_sessions().get(name)
        if not snapshot:
            msg = f"セッションが見つかりません: {name}"
            raise ValueError(msg)

        state = state_from_dict(snapshot["state"])
        cart = [
            CartLine(code=item.id, name=item.name or item.id, price=item.price or 0, count=item.count)
            for item in state.cart
        ]
        http = make_http(snapshot.get("cookies", []))
        try:
            client = SaizeriyaClient(initial_state=state, http=http)
        except Exception:
            http.close()
            raise
        # The saved cart is the TUI's pending cart; the client rebuilds it at submit time.
        while client.get_state().cart:
            client.remove_cart_item(0)
        return cls(
            name=name,
            http=http,
            client=client,
            created_at=int(snapshot.get("createdAt", time.time() * 1000)),
            cart=cart,
        )

    def save(self) -> None:
        """Persist the session, carrying the pending cart in the snapshot."""
        state = self.client.get_state()
        state.cart = [
            CartItem(
                id=line.code,
                name=line.name,
                price=line.price,
                count=line.count,
                reorder=0,
                mod_id="",
                mod_count=0,
            )
            for line in self.cart
        ]
        save_session(self.name, self.http, state, self.created_at)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self.http.close()

    # --- state ------------------------------------------------------------

    @property
    def state(self) -> ClientState:
        """Return the current client state snapshot."""
        return self.client.get_state()

    @property
    def total_count(self) -> int:
        """Return the number of pending items."""
        return sum(line.count for line in self.cart)

    @property
    def total_price(self) -> int:
        """Return the pending cart total in yen."""
        return sum(line.subtotal for line in self.cart)

    def set_people_count(self, count: int) -> ClientState:
        """Set the table's people count."""
        state = self.client.set_people_count(count)
        self.save()
        return state

    # --- menu -------------------------------------------------------------

    def lookup(self, code: str, fallback: MenuItem | None = None) -> MenuItem:
        """Confirm `code` against the official system and return it as a menu item."""
        result: dict[str, Any] = self.client.lookup_item(code)
        item_data = result.get("item_data")
        if result.get("result") != "OK" or not item_data or item_data.get("state") == 0:
            raise ItemUnavailableError(code)

        name = str(item_data.get("name") or code)
        tags = sorted({*(fallback.tags if fallback else []), "公式確認済み"})
        return MenuItem(
            code=code,
            name=name,
            kana=name,
            price=int(item_data.get("price") or 0),
            category=fallback.category if fallback else "入力済み",
            tags=tags,
            alcohol_check=result.get("alcohol_check"),
            source="official",
        )

    # --- cart -------------------------------------------------------------

    def find_line(self, code: str) -> CartLine | None:
        """Return the pending cart line for `code`, if any."""
        return next((line for line in self.cart if line.code == code), None)

    def add_to_cart(self, item: MenuItem, count: int = 1) -> CartLine:
        """Add `count` of `item` to the pending cart, merging by code."""
        line = self.find_line(item.code)
        next_count = (line.count if line else 0) + count
        if next_count > MAX_ITEM_COUNT:
            raise CartLimitError
        if line:
            line.name = item.name
            line.price = item.price
            line.count = next_count
        else:
            line = CartLine(code=item.code, name=item.name, price=item.price, count=count)
            self.cart.append(line)
        self.save()
        return line

    def set_count(self, code: str, count: int) -> None:
        """Set the pending quantity for `code`, removing the line at zero."""
        line = self.find_line(code)
        if line is None:
            return
        if count <= 0:
            self.cart.remove(line)
        elif count > MAX_ITEM_COUNT:
            raise CartLimitError
        else:
            line.count = count
        self.save()

    def clear_cart(self) -> None:
        """Drop every pending cart line."""
        self.cart.clear()
        self.save()

    # --- actions ----------------------------------------------------------

    def submit_order(self) -> ClientState:
        """Push the pending cart to the official system and submit it.

        Every line is re-checked first: anything the official system no longer
        serves is dropped from the cart and reported, so a half-added order is
        never left behind on the server.
        """
        if not self.cart:
            msg = "注文かごが空です"
            raise ValueError(msg)

        dropped = [line for line in self.cart if not self._is_orderable(line.code)]
        if dropped:
            for line in dropped:
                self.cart.remove(line)
            self.save()
            raise UnavailableLinesError(dropped)

        try:
            for line in self.cart:
                self.client.add_item(line.code, count=line.count)
        except Exception:
            self._reset_client_cart()
            raise

        state = self.client.submit_order()
        self.cart.clear()
        self.save()
        return state

    def _is_orderable(self, code: str) -> bool:
        try:
            self.lookup(code)
        except ItemUnavailableError:
            return False
        return True

    def _reset_client_cart(self) -> None:
        while self.client.get_state().cart:
            self.client.remove_cart_item(0)

    def get_account(self) -> AccountSummary:
        """Fetch the account summary."""
        _, account = self.client.get_account()
        self.save()
        return account

    def get_receipt(self) -> tuple[AccountSummary, ReceiptSummary]:
        """Settle the bill and fetch the receipt barcode."""
        _, account, receipt = self.client.get_receipt()
        self.save()
        return account, receipt

    def call_staff(self, *, dessert: bool = False) -> dict[str, Any]:
        """Call staff, optionally for dessert service."""
        return self.client.call(after=dessert)
