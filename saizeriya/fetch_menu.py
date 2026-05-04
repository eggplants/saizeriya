"""Crawl Saizeriya's per-shop menu by probing item codes.

Mirrors `nodejs/saizeriya/scripts/get-all-menu.ts`: POSTs to the
`saizeriya2/src/cmd/get_item.php` endpoint for every (shop, item code) pair,
appending discovered items to a JSON file that can be resumed across runs.
"""

from __future__ import annotations

from .shops import SHOPS

import json
import random
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

FETCH_URL = "https://ioes.saizeriya.co.jp/saizeriya2/src/cmd/get_item.php"
DEFAULT_OUTPUT = Path("data/menu-by-shop.json")
DEFAULT_TABLE_NO = "1"
DEFAULT_LANGUAGE = "1"
DEFAULT_PEOPLE_COUNT = "3"
DEFAULT_ITEM_CODE_COUNT = 10000

REQUEST_HEADERS = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "origin": "https://ioes.saizeriya.co.jp",
    "referer": "https://ioes.saizeriya.co.jp/saizeriya2/",
    "x-requested-with": "XMLHttpRequest",
}


ResultMap = dict[str, dict[str, dict[str, Any]]]


def fetch_item(
    shop_id: str,
    item_code: int,
    *,
    http: httpx.Client,
    table_no: str = DEFAULT_TABLE_NO,
    language: str = DEFAULT_LANGUAGE,
    people_count: str = DEFAULT_PEOPLE_COUNT,
) -> dict[str, Any]:
    """POST to `get_item.php` and return the parsed JSON response."""
    item_id = f"{item_code:04d}"
    response = http.post(
        FETCH_URL,
        data={
            "sid": shop_id,
            "tno": table_no,
            "lng": language,
            "id": item_id,
            "num": people_count,
        },
        headers=REQUEST_HEADERS,
    )
    response.raise_for_status()
    return response.json()


def read_existing_results(path: Path) -> ResultMap:
    """Load a previous menu dump or return an empty mapping."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_results(path: Path, results: ResultMap) -> None:
    """Atomically replace `path` with a pretty-printed JSON dump of `results`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")


def collect_known_item_ids(results: ResultMap) -> set[str]:
    """Return the set of item ids already discovered across all shops."""
    ids: set[str] = set()
    for shop_items in results.values():
        for item_id, result in shop_items.items():
            data = result.get("item_data") if isinstance(result, dict) else None
            ids.add(data["id"] if isinstance(data, dict) and data.get("id") else item_id)
    return ids


def crawl(  # noqa: PLR0913
    shops: Iterable[str] = SHOPS,
    *,
    out: Path = DEFAULT_OUTPUT,
    item_code_count: int = DEFAULT_ITEM_CODE_COUNT,
    table_no: str = DEFAULT_TABLE_NO,
    language: str = DEFAULT_LANGUAGE,
    people_count: str = DEFAULT_PEOPLE_COUNT,
    shuffle: bool = True,
    http: httpx.Client | None = None,
    log: Callable[[str], None] = print,
) -> ResultMap:
    """Crawl `shops` × `item_code_count`, persisting incrementally to `out`.

    Resumes from any existing data in `out` by skipping known item codes.
    """
    results = read_existing_results(out)
    known = collect_known_item_ids(results)

    shop_list = list(shops)
    if shuffle:
        random.shuffle(shop_list)

    own_http = http is None
    client = http if http is not None else httpx.Client()

    total = len(shop_list) * item_code_count
    skipped = 0
    attempts = 0

    try:
        for shop_id in shop_list:
            shop_items = results.setdefault(shop_id, {})
            for code in range(item_code_count):
                item_id = f"{code:04d}"
                if item_id in known:
                    skipped += 1
                    continue
                attempts += 1
                try:
                    result = fetch_item(
                        shop_id,
                        code,
                        http=client,
                        table_no=table_no,
                        language=language,
                        people_count=people_count,
                    )
                except httpx.HTTPError as exc:
                    log(f"Failed to fetch {shop_id}/{item_id}: {exc}")
                    continue
                log(f"Fetched {shop_id}/{item_id}")
                if not result.get("item_data"):
                    continue
                shop_items[item_id] = result
                known.add(item_id)
                log(f"Found item {item_id} for shop {shop_id}")
            write_results(out, results)
            log(
                f"Finished shop {shop_id}: skipped {skipped}, attempts {attempts}/{total}, found {len(known)}",
            )
    finally:
        if own_http:
            client.close()

    write_results(out, results)
    return results
