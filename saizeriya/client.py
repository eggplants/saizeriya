"""Synchronous client for Saizeriya's mobile ordering pages."""

import copy
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

import httpx

from .forms import (
    FORM_CONTENT_TYPE,
    create_base_fields,
    create_order_submit_body,
    encode_form,
    now_order_time,
)
from .page_parser import PageParser
from .process_qr import process_qr
from .types import (
    AccountSummary,
    CartItem,
    ClientState,
    ReceiptSummary,
)

if TYPE_CHECKING:
    from types import TracebackType

    from typing_extensions import Self

_CODE_PATTERN = re.compile(r"^\d{4}$")


class SaizeriyaClient:
    """Drives a Saizeriya ordering session from a QR URL or restored state."""

    def __init__(
        self,
        qr_url_source: str | None = None,
        *,
        people_count: int | None = None,
        initial_state: ClientState | None = None,
        http: httpx.Client | None = None,
    ) -> None:
        """Initialize the client with either a QR URL or a previous state snapshot."""
        self._http = http if http is not None else httpx.Client(follow_redirects=True)
        self._owns_http = http is None

        if initial_state is not None:
            self._state = ClientState(
                base_url=initial_state.base_url,
                next_id=initial_state.next_id,
                shop_id=initial_state.shop_id,
                table_no=initial_state.table_no,
                people_count=initial_state.people_count,
                page_kind=initial_state.page_kind,
                token=initial_state.token,
                session_id=initial_state.session_id,
                cart=[copy.copy(item) for item in initial_state.cart],
            )
        else:
            if qr_url_source is None:
                msg = "qr_url_source is required when initial_state is not provided"
                raise ValueError(msg)
            processed = process_qr(qr_url_source, self._http)
            resolved_people = people_count if people_count is not None else (processed.people_count or 0)
            self._state = ClientState(
                base_url=processed.base_url,
                next_id=processed.id,
                shop_id=processed.shop_id,
                table_no=processed.table_no,
                people_count=resolved_people,
                page_kind=processed.page_kind,
            )

        if people_count is not None:
            self.set_people_count(people_count)

    # ----- lifecycle -----

    def close(self) -> None:
        """Close the underlying HTTP client when owned by this instance."""
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> Self:  # noqa: D105
        return self

    def __exit__(  # noqa: D105
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        self.close()

    # ----- state inspection -----

    def get_state(self) -> ClientState:
        """Return a deep copy of the current client state."""
        return ClientState(
            base_url=self._state.base_url,
            next_id=self._state.next_id,
            shop_id=self._state.shop_id,
            table_no=self._state.table_no,
            people_count=self._state.people_count,
            page_kind=self._state.page_kind,
            token=self._state.token,
            session_id=self._state.session_id,
            cart=[copy.copy(item) for item in self._state.cart],
        )

    # ----- internals -----

    def _command_url(self, path: str) -> str:
        return urljoin(self._state.base_url, path)

    def _page_url(self) -> str:
        return f"{self._state.base_url}?{self._state.next_id}"

    def _update_from_page(self, parser: PageParser) -> None:
        self._state.next_id = parser.get_next_action_id()
        token = parser.get_token()
        if token is not None:
            self._state.token = token
        session_id = parser.get_session_id()
        if session_id is not None:
            self._state.session_id = session_id
        self._state.page_kind = parser.get_page_kind()
        people = parser.get_people_count()
        if people is not None:
            self._state.people_count = people

    def _submit_page(self, fields: dict[str, Any]) -> PageParser:
        response = self._http.post(
            self._page_url(),
            content=encode_form(fields),
            headers={"content-type": FORM_CONTENT_TYPE},
        )
        parser = PageParser(response.text)
        self._update_from_page(parser)
        return parser

    def _post_json(self, path: str, fields: dict[str, Any]) -> dict[str, Any]:
        response = self._http.post(
            self._command_url(path),
            content=encode_form(fields),
            headers={"content-type": FORM_CONTENT_TYPE},
        )
        return response.json()

    def _require_token(self) -> str:
        if not self._state.token:
            msg = "Token not found. Move to a token-bearing page first."
            raise ValueError(msg)
        return self._state.token

    def _move_to_number_page(self, *, forced: bool = True) -> PageParser:
        return self._submit_page(
            {
                **create_base_fields("number"),
                "ctrl": "forced" if forced else "",
            }
        )

    # ----- public actions -----

    def set_people_count(self, count: int) -> ClientState:
        """Set the number of people for this table."""
        if not isinstance(count, int) or isinstance(count, bool) or count < 1 or count > 99:  # noqa: PLR2004
            msg = "People count must be an integer between 1 and 99"
            raise ValueError(msg)
        if self._state.page_kind != "number":
            self._move_to_number_page(forced=True)
        self._submit_page(
            {
                **create_base_fields("menu", self._require_token()),
                "ctrl": "number",
                "number": count,
            }
        )
        self._state.people_count = count
        return self.get_state()

    def lookup_item(self, code: str) -> dict[str, Any]:
        """Look up an item by its 4-digit code."""
        if not _CODE_PATTERN.match(code):
            msg = "Item code must be 4 digits"
            raise ValueError(msg)
        return self._post_json(
            "./src/cmd/get_item.php",
            {
                "sid": self._state.shop_id,
                "tno": self._state.table_no,
                "lng": "1",
                "id": code,
                "num": self._state.people_count,
                "ssid": self._state.session_id or "",
            },
        )

    def add_item(
        self,
        code: str,
        *,
        count: int = 1,
        mod_id: str = "",
        mod_count: int = 0,
        reorder: bool = False,
    ) -> ClientState:
        """Add an item to the local cart after server-side availability check."""
        if not _CODE_PATTERN.match(code):
            msg = "Item code must be 4 digits"
            raise ValueError(msg)
        if not isinstance(count, int) or isinstance(count, bool) or count < 1 or count > 99:  # noqa: PLR2004
            msg = "Item count must be an integer between 1 and 99"
            raise ValueError(msg)

        item = self._post_json(
            "./src/cmd/get_item.php",
            {
                "sid": self._state.shop_id,
                "tno": self._state.table_no,
                "lng": "1",
                "id": code,
                "num": self._state.people_count,
                "ssid": self._state.session_id or "",
            },
        )
        if item.get("result") != "OK" or not item.get("item_data"):
            msg = f"Item {code} was not found"
            raise ValueError(msg)
        item_data = item["item_data"]
        if item_data.get("state") == 0:
            msg = f"Item {code} is sold out"
            raise ValueError(msg)

        self._submit_page(
            {
                **create_base_fields("main", self._require_token()),
                "ctrl": "add",
                "ord-drkbar-cnt": "0",  # cspell:words drkbar
                "is_reorder": "1" if reorder else "0",
                "order-time": now_order_time(),
                "code": code,
                "amount": count,
                "mod_code": mod_id,
                "mod_amount": mod_count,
            }
        )

        self._state.cart.append(
            CartItem(
                id=code,
                name=item_data.get("name"),
                price=item_data.get("price"),
                count=count,
                reorder=1 if reorder else 0,
                mod_id=mod_id,
                mod_count=mod_count,
            ),
        )
        return self.get_state()

    def go_to_menu(self) -> ClientState:
        """Navigate to the menu page."""
        self._submit_page(create_base_fields("menu"))
        return self.get_state()

    def go_to_cart(self) -> ClientState:
        """Navigate to the cart (main) page."""
        self._submit_page(create_base_fields("main", self._state.token))
        return self.get_state()

    def go_to_history(self) -> ClientState:
        """Navigate to the order history page."""
        self._submit_page(
            {
                **create_base_fields("history", self._state.token),
                "ctrl": "remember",
                "code": "",
                "drinkbar-cnt": "0",  # cspell:words drinkbar
                "alcohol-cnt": "0",
                "ord-drkbar-cnt": "0",  # cspell:words drkbar
            }
        )
        return self.get_state()

    def go_to_account(self) -> ClientState:
        """Navigate to the account page."""
        self._submit_page(create_base_fields("account", self._state.token))
        return self.get_state()

    def get_account(self) -> tuple[ClientState, AccountSummary]:
        """Navigate to the account page and return its summary."""
        parser = self._submit_page(create_base_fields("account", self._state.token))
        return self.get_state(), parser.get_account_summary()

    def show_receipt(self) -> ClientState:
        """Navigate to the receipt page."""
        self._submit_page(create_base_fields("receipt"))
        return self.get_state()

    def get_receipt(self) -> tuple[ClientState, AccountSummary, ReceiptSummary]:
        """Navigate to the receipt page and return its account/receipt summary."""
        parser = self._submit_page(create_base_fields("receipt"))
        return (
            self.get_state(),
            parser.get_account_summary(),
            parser.get_receipt_summary(),
        )

    def reorder(self, code: str) -> ClientState:
        """Trigger a reorder action on the menu page."""
        self._submit_page(
            {
                **create_base_fields("menu"),
                "ctrl": "reorder",
                "code": code,
            }
        )
        return self.get_state()

    def remove_cart_item(self, index: int) -> ClientState:
        """Remove the cart entry at `index` (0-based)."""
        if not isinstance(index, int) or isinstance(index, bool) or index < 0 or index >= len(self._state.cart):
            msg = "Cart item was not found"
            raise ValueError(msg)
        del self._state.cart[index]
        return self.get_state()

    def submit_order(self) -> ClientState:
        """Submit the local cart as an order to the server."""
        if not self._state.cart:
            msg = "Cannot submit an empty cart"
            raise ValueError(msg)
        token = self._require_token()
        body = create_order_submit_body(token, self._state.cart)
        response = self._http.post(
            self._page_url(),
            content=body,
            headers={"content-type": FORM_CONTENT_TYPE},
        )
        parser = PageParser(response.text)
        self._update_from_page(parser)
        self._state.cart = []
        return self.get_state()

    def call(self, *, after: bool = False) -> dict[str, Any]:
        """Call staff (after=False) or request dessert service (after=True)."""
        return self._post_json(
            "./src/cmd/tbl_call.php",
            {
                "sid": self._state.shop_id,
                "tbl": self._state.table_no,
                "aft": after,
            },
        )

    def call_staff(self) -> dict[str, Any]:
        """Call staff for assistance."""
        return self.call(after=False)

    def call_dessert(self) -> dict[str, Any]:
        """Request dessert service."""
        return self.call(after=True)

    def check_order_started(self) -> dict[str, Any]:
        """Check whether ordering has started for this table."""
        return self._post_json(
            "./src/cmd/check_order.php",
            {"sid": self._state.shop_id, "tno": self._state.table_no},
        )

    def check_last_order(self) -> dict[str, Any]:
        """Check the last-order time window."""
        return self._post_json(
            "./src/cmd/check_lastorder.php",  # cspell:words lastorder
            {"sid": self._state.shop_id},
        )

    def check_midnight(self) -> dict[str, Any]:
        """Check the midnight cutoff."""
        return self._post_json(
            "./src/cmd/check_midnight.php",
            {"sid": self._state.shop_id},
        )

    def confirm_alcohol(self) -> dict[str, Any]:
        """Confirm alcohol availability for the session."""
        return self._post_json(
            "./src/cmd/put_alcohol.php",
            {
                "sid": self._state.shop_id,
                "tno": self._state.table_no,
                "ssid": self._state.session_id or "",
            },
        )
