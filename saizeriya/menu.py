"""Seed menu data plus search, availability and classification helpers.

The logic here mirrors `betterzeriya`'s `menu-search`, `menu-availability` and
`menu-classification` modules so the TUI can filter a bundled menu snapshot
without hitting the network. Live availability is still confirmed through
`SaizeriyaClient.lookup_item` before an item is added to the cart.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal

MenuServicePeriod = Literal["lunch", "regular"]

DEFAULT_MENU_PATH = Path(__file__).parent / "data" / "menu.json"

ALL_CATEGORY = "すべて"

_CODE_PATTERN = re.compile(r"^\d{4}$")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_NUMERIC_PATTERN = re.compile(r"^\d+$")

_JST = timezone(timedelta(hours=9))

CURRENT_LUNCH_ENTREE_CODES = frozenset(
    {"1116", "1120", "1135", "1140", "1141", "1142", "1145", "1170", "1171", "1172", "1175"},
)
CURRENT_LUNCH_SERVICE_CODES = frozenset({"1199", "1999", "5101"})
LUNCH_ONLY_SERVICE_CODES = frozenset({"1199", "1999"})
CURRENT_LUNCH_CODES = CURRENT_LUNCH_ENTREE_CODES | CURRENT_LUNCH_SERVICE_CODES

_LUNCH_END_MINUTES = 15 * 60


@dataclass
class MenuItem:
    """A single orderable menu entry."""

    code: str
    name: str
    kana: str
    price: int
    category: str
    tags: list[str] = field(default_factory=list)
    alcohol_check: int | None = None
    source: Literal["seed", "official"] = "seed"


def load_menu(path: Path | None = None) -> list[MenuItem]:
    """Load and normalize the bundled seed menu (or a compatible JSON file)."""
    raw = json.loads((path or DEFAULT_MENU_PATH).read_text(encoding="utf-8"))
    items: list[MenuItem] = []
    for entry in raw:
        code = str(entry.get("code", "")).strip()
        name = str(entry.get("name", "")).strip()
        if not _CODE_PATTERN.match(code) or not name:
            continue
        items.append(
            MenuItem(
                code=code,
                name=name,
                kana=str(entry.get("kana") or name),
                price=int(entry.get("price") or 0),
                category=str(entry.get("category") or "メニュー"),
                tags=list(entry.get("tags") or []),
                alcohol_check=entry.get("alcoholCheck"),
            ),
        )
    return items


# --- search ---------------------------------------------------------------


def normalize_menu_search_text(value: str) -> str:
    """Normalize text to NFKC lowercase without whitespace for comparison."""
    return _WHITESPACE_PATTERN.sub("", unicodedata.normalize("NFKC", value).lower())


def _search_tokens(query: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", query).lower().strip()
    return [token for token in _WHITESPACE_PATTERN.split(normalized) if token]


def _fuzzy_distance_limit(query_length: int) -> int:
    if query_length <= 2:  # noqa: PLR2004
        return 0
    if query_length <= 4:  # noqa: PLR2004
        return 1
    if query_length <= 8:  # noqa: PLR2004
        return 2
    return 3


def _includes_in_order(query: str, text: str) -> bool:
    query_index = 0
    for character in text:
        if character == query[query_index]:
            query_index += 1
            if query_index == len(query):
                return True
    return False


def _edit_distance(a: str, b: str, max_distance: int) -> int:
    if abs(len(a) - len(b)) > max_distance:
        return max_distance + 1

    previous = list(range(len(b) + 1))
    for a_index in range(1, len(a) + 1):
        current = [a_index] + [0] * len(b)
        row_min = current[0]
        for b_index in range(1, len(b) + 1):
            cost = 0 if a[a_index - 1] == b[b_index - 1] else 1
            current[b_index] = min(
                previous[b_index] + 1,
                current[b_index - 1] + 1,
                previous[b_index - 1] + cost,
            )
            row_min = min(row_min, current[b_index])
        if row_min > max_distance:
            return max_distance + 1
        previous = current

    return previous[len(b)]


def _has_near_substring(query: str, text: str) -> bool:
    max_distance = _fuzzy_distance_limit(len(query))
    if max_distance == 0:
        return False

    shortest_window = max(1, len(query) - max_distance)
    longest_window = min(len(text), len(query) + max_distance)

    for window_length in range(shortest_window, longest_window + 1):
        for start in range(len(text) - window_length + 1):
            candidate = text[start : start + window_length]
            if _edit_distance(query, candidate, max_distance) <= max_distance:
                return True

    return False


def _token_matches_text(token: str, text: str) -> bool:
    if not token or not text:
        return False
    if token in text:
        return True
    if len(token) >= 3 and _includes_in_order(token, text):  # noqa: PLR2004
        return True
    return _has_near_substring(token, text)


def matches_menu_search(item: MenuItem, query: str) -> bool:
    """Return whether `item` matches a (possibly fuzzy, multi-token) query."""
    tokens = _search_tokens(query)
    if not tokens:
        return True

    code = normalize_menu_search_text(item.code)
    text_fields = [normalize_menu_search_text(value) for value in (item.name, item.kana, item.category, *item.tags)]

    for token in tokens:
        normalized = normalize_menu_search_text(token)
        if _NUMERIC_PATTERN.match(normalized):
            if normalized not in code:
                return False
            continue
        if normalized in code:
            continue
        if not any(_token_matches_text(normalized, field) for field in text_fields):
            return False

    return True


# --- availability ---------------------------------------------------------


def is_lunch_period(now: datetime | None = None) -> bool:
    """Return whether Tokyo local time is inside the weekday lunch window."""
    moment = (now or datetime.now(tz=_JST)).astimezone(_JST)
    is_weekday = moment.weekday() <= 4  # noqa: PLR2004
    return is_weekday and moment.hour * 60 + moment.minute < _LUNCH_END_MINUTES


def get_menu_service_period(now: datetime | None = None) -> MenuServicePeriod:
    """Return the currently active menu service period."""
    return "lunch" if is_lunch_period(now) else "regular"


def is_current_lunch_menu_item(item: MenuItem) -> bool:
    """Return whether the item belongs to the current lunch line-up."""
    return item.code in CURRENT_LUNCH_CODES


def is_lunch_named_menu_item(item: MenuItem) -> bool:
    """Return whether the item is labelled as a lunch item."""
    return item.category == "ランチ" or "ﾗﾝﾁ" in item.name or "ランチ" in item.name


def is_stale_lunch_menu_item(item: MenuItem) -> bool:
    """Return whether the item is a lunch item that is no longer offered."""
    return is_lunch_named_menu_item(item) and not is_current_lunch_menu_item(item)


def is_lunch_only_menu_item(item: MenuItem) -> bool:
    """Return whether the item can only be ordered during lunch hours."""
    return (
        item.code in CURRENT_LUNCH_ENTREE_CODES
        or item.code in LUNCH_ONLY_SERVICE_CODES
        or is_stale_lunch_menu_item(item)
    )


def get_display_category(item: MenuItem, period: MenuServicePeriod) -> str:
    """Return the category label to show for the given service period."""
    if period == "lunch" and is_current_lunch_menu_item(item):
        return "ランチ"
    return item.category


def filter_menu_for_service_period(items: list[MenuItem], period: MenuServicePeriod) -> list[MenuItem]:
    """Drop retired lunch entries and, outside lunch hours, lunch-only entries."""
    visible = [item for item in items if not is_stale_lunch_menu_item(item)]
    if period == "regular":
        visible = [item for item in visible if not is_lunch_only_menu_item(item)]
    return [replace(item, category=get_display_category(item, period)) for item in visible]


# --- classification -------------------------------------------------------


def _normalize_classification_text(value: str) -> str:
    return _WHITESPACE_PATTERN.sub("", unicodedata.normalize("NFKC", value)).upper()


_NON_ALCOHOL_KEYWORDS = tuple(
    _normalize_classification_text(keyword) for keyword in ("ノンアルコール", "ノンアル", "NONALCOHOL", "NON-ALCOHOL")
)

_ALCOHOL_KEYWORDS = tuple(
    _normalize_classification_text(keyword)
    for keyword in (
        "アルコール",
        "お酒",
        "酒類",
        "ワイン",
        "ビール",
        "ジョッキ",
        "サワー",
        "ハイボール",
        "ウイスキー",
        "ウィスキー",
        "焼酎",
        "日本酒",
        "カクテル",
        "シャンパン",
        "スパークリング",
        "デカンタ",
        "マグナム",
        "ランブルスコ",
        "キャンティ",
        "ベルデッキオ",
        "ドンラファエロ",
        "グラッパ",
        "氷結",
    )
)


def is_alcohol_menu_item(item: MenuItem) -> bool:
    """Return whether the item is alcoholic, preferring the official flag."""
    if item.alcohol_check is not None:
        return item.alcohol_check == 1

    fields = (item.name, item.kana, item.category, *item.tags)
    text = " ".join(_normalize_classification_text(value) for value in fields)
    if not text.strip() or any(keyword in text for keyword in _NON_ALCOHOL_KEYWORDS):
        return False
    return any(keyword in text for keyword in _ALCOHOL_KEYWORDS)


@lru_cache(maxsize=1)
def default_menu() -> tuple[MenuItem, ...]:
    """Return the bundled seed menu, loaded once per process."""
    return tuple(load_menu())
