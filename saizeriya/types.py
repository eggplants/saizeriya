"""Data types for the Saizeriya client."""

from dataclasses import dataclass, field
from typing import Literal

PageKind = Literal[
    "top",
    "number",
    "menu",
    "main",
    "history",
    "call",
    "account",
    "receipt",
    "unknown",
]


@dataclass
class CartItem:
    """A single item queued for order submission."""

    id: str
    count: int
    reorder: int
    mod_id: str
    mod_count: int
    name: str | None = None
    price: int | None = None


@dataclass
class AccountLine:
    """One row in the account summary table."""

    name: str
    count: int
    price: int


@dataclass
class AccountSummary:
    """Aggregate of submitted items shown on the account page."""

    lines: list[AccountLine]
    count: int
    total: int
    control_no: str | None = None
    dummy_no: str | None = None


@dataclass
class ReceiptSummary:
    """Barcode info shown on the receipt page."""

    barcode_value: str | None = None
    barcode_image_src: str | None = None


@dataclass
class ClientState:
    """Snapshot of the client's view of the ordering session."""

    base_url: str
    next_id: str
    shop_id: int
    table_no: int
    people_count: int
    page_kind: PageKind
    cart: list[CartItem] = field(default_factory=list)
    token: str | None = None
    session_id: str | None = None
