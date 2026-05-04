"""HTML parsing for Saizeriya's ordering pages."""

from __future__ import annotations

import re
from typing import cast, get_args

from bs4 import BeautifulSoup, Tag

from .types import AccountLine, AccountSummary, PageKind, ReceiptSummary

_KNOWN_PAGE_KINDS = frozenset(get_args(PageKind)) - {"unknown"}


def _attr_str(node: Tag, name: str) -> str | None:
    value = node.get(name)
    if value is None:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return value


class PageParser:
    """Parse a Saizeriya ordering page and extract state."""

    def __init__(self, html: str) -> None:
        self.root = BeautifulSoup(html, "lxml")

    def get_optional_input_value(self, selector: str) -> str | None:
        """Return the value attribute of the first match, or None."""
        node = self.root.select_one(selector)
        if not isinstance(node, Tag):
            return None
        return _attr_str(node, "value")

    def get_input_value(self, selector: str, label: str) -> str:
        """Return the value attribute of the first match, raising if absent."""
        value = self.get_optional_input_value(selector)
        if value is None:
            msg = f"{label} value not found"
            raise ValueError(msg)
        return value

    def get_shop_id(self) -> int:
        """Read the shop id input as an integer."""
        return int(self.get_input_value('input[id="shop-id"]', "Shop ID"))

    def get_table_no(self) -> int:
        """Read the table number input as an integer."""
        return int(self.get_input_value('input[id="table-no"]', "Table number"))

    def get_token(self) -> str | None:
        """Return the request CSRF token if present."""
        return self.get_optional_input_value('input[name="token"]')

    def get_session_id(self) -> str | None:
        """Return the session id if present."""
        return self.get_optional_input_value('input[id="session-id"]')

    def get_people_count(self) -> int | None:
        """Return the table's people count from either the input or the top page label."""
        value = self.get_optional_input_value('input[id="number"]')
        if value:
            return int(value)
        node = self.root.select_one("#number")
        if node is None:
            return None
        match = re.search(r"(\d+)\s*名", node.get_text(strip=True))
        return int(match.group(1)) if match else None

    def get_page_kind(self) -> PageKind:
        """Identify which page kind is currently rendered."""
        form = self.root.select_one('form[id="frm_ctrl"]')
        if not isinstance(form, Tag):
            return "unknown"
        cls = form.get("class")
        if not cls:
            return "unknown"
        classes = cls if isinstance(cls, list) else cls.split()
        page_class = next((c for c in classes if c.endswith("-page")), None)
        if not page_class:
            return "unknown"
        kind = page_class[: -len("-page")]
        if kind in _KNOWN_PAGE_KINDS:
            return cast("PageKind", kind)
        return "unknown"

    def get_next_action_id(self) -> str:
        """Return the id appended to the form action URL."""
        form = self.root.select_one('form[id="frm_ctrl"]')
        if not isinstance(form, Tag):
            msg = 'Form with id "frm_ctrl" not found'
            raise ValueError(msg)
        action = _attr_str(form, "action")
        if not action:
            msg = "Form action attribute not found"
            raise ValueError(msg)
        parts = action.split("?", 1)
        if len(parts) < 2 or not parts[1]:
            msg = "No action id found in form action"
            raise ValueError(msg)
        return parts[1]

    def get_account_summary(self) -> AccountSummary:
        """Extract the account summary table and totals."""
        html = str(self.root)
        m_ctrl = re.search(r"\[control_no\]\s*=>\s*(\S+)", html)
        m_dum = re.search(r"\[dummy_no\]\s*=>\s*(\S+)", html)

        lines: list[AccountLine] = []
        for row in self.root.select("#body-section .list-base table tbody tr"):
            cells = row.select("td")
            if len(cells) < 3:
                continue
            name = cells[0].get_text(strip=True)
            count_text = cells[1].get_text(strip=True) or "0"
            price_text = (cells[2].get_text(strip=True) or "0").replace(",", "")
            try:
                count = int(count_text)
                price = int(price_text)
            except ValueError:
                continue
            if not name:
                continue
            lines.append(AccountLine(name=name, count=count, price=price))

        count_node = self.root.select_one("#body-section .amount .count span")
        if count_node is not None:
            try:
                count_total = int(count_node.get_text(strip=True))
            except ValueError:
                count_total = sum(line.count for line in lines)
        else:
            count_total = sum(line.count for line in lines)

        total_node = self.root.select_one("#body-section .amount .amount span")
        if total_node is not None:
            try:
                total = int(total_node.get_text(strip=True).replace(",", ""))
            except ValueError:
                total = sum(line.price for line in lines)
        else:
            total = sum(line.price for line in lines)

        return AccountSummary(
            lines=lines,
            count=count_total,
            total=total,
            control_no=m_ctrl.group(1) if m_ctrl else None,
            dummy_no=m_dum.group(1) if m_dum else None,
        )

    def get_receipt_summary(self) -> ReceiptSummary:
        """Extract the barcode payload from the receipt page."""
        img = self.root.select_one(".receipt-page .barcode img")
        p_node = self.root.select_one(".receipt-page .barcode p")
        src = _attr_str(img, "src") if isinstance(img, Tag) else None
        text = p_node.get_text(strip=True) if p_node is not None else None
        if text:
            text = re.sub(r"\s", "", text)
        return ReceiptSummary(
            barcode_value=text or None,
            barcode_image_src=src or None,
        )
