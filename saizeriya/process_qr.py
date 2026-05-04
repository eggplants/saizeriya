"""Resolve a Saizeriya QR URL into the initial ordering page state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

from .page_parser import PageParser

if TYPE_CHECKING:
    import httpx

    from .types import PageKind


@dataclass
class ProcessedQR:
    """Initial state derived from following the QR redirect chain."""

    id: str
    base_url: str
    shop_id: int
    table_no: int
    people_count: int | None
    page_kind: PageKind


def process_qr(qr_url: str, http: httpx.Client) -> ProcessedQR:
    """Fetch the QR redirect target and parse it into a `ProcessedQR`."""
    qr_response = http.get(qr_url, follow_redirects=False)
    location = qr_response.headers.get("location")
    if not location:
        msg = "No redirect location found"
        raise ValueError(msg)
    next_url = urljoin(qr_url, location)

    response = http.get(next_url, follow_redirects=True)
    parser = PageParser(response.text)
    parsed = urlparse(next_url)

    return ProcessedQR(
        id=parser.get_next_action_id(),
        base_url=f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
        shop_id=parser.get_shop_id(),
        table_no=parser.get_table_no(),
        people_count=parser.get_people_count(),
        page_kind=parser.get_page_kind(),
    )
