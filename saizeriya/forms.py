"""Helpers to build URL-encoded form payloads sent to the ordering pages."""

from datetime import datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .types import CartItem


FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"


def now_order_time() -> str:
    """Format the current local time as `YYYY/MM/DD,HH:MM:SS`."""
    return datetime.now().strftime("%Y/%m/%d,%H:%M:%S")  # noqa: DTZ005


def create_base_fields(proc: str, token: str | None = None) -> dict[str, str]:
    """Return the common form fields posted to every page transition."""
    fields: dict[str, str] = {
        "proc": proc,
        "ctrl": "",
        "sub_ctrl": "",
        "cur_lang": "1",
        "message": "",
    }
    if token:
        fields["token"] = token
    return fields


def to_form_pairs(fields: dict[str, Any]) -> list[tuple[str, str]]:
    """Flatten a mixed-type field map into URL-encoded form pairs."""
    result: list[tuple[str, str]] = []
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, bool):
            result.append((key, "true" if value else "false"))
        else:
            result.append((key, str(value)))
    return result


def encode_form(fields: dict[str, Any]) -> bytes:
    """URL-encode a field map for use as an HTTP request body."""
    return urlencode(to_form_pairs(fields), doseq=True).encode("utf-8")


def create_order_submit_body(token: str, cart: Sequence[CartItem]) -> bytes:
    """Build the URL-encoded body for a final order submission."""
    fields: dict[str, Any] = {
        **create_base_fields("order", token),
        "ctrl": "remember",
        "code": "",
        "drinkbar-cnt": "0",
        "alcohol-cnt": "0",
        "ord-drkbar-cnt": "0",
    }
    pairs = to_form_pairs(fields)
    for item in cart:
        pairs.append(("item[id][]", item.id))
        pairs.append(("item[reorder][]", str(item.reorder)))
        pairs.append(("item[count][]", str(item.count)))
        pairs.append(("item[mod_id][]", item.mod_id))
        pairs.append(("item[mod_count][]", str(item.mod_count)))
    return urlencode(pairs, doseq=True).encode("utf-8")
