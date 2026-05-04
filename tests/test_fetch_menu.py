from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qsl

import httpx

from saizeriya import fetch_menu


def _item_payload(item_id: str, name: str = "Dish", price: int = 100) -> dict:
    return {
        "result": "OK",
        "item_data": {
            "id": item_id,
            "name": name,
            "price": price,
            "messages": [],
            "mod_id": "",
            "mod_name": "",
            "mod_price": 0,
            "mod_ini_cnt": 0,
            "mod_guid": "",
            "drk_id": "",
            "drk_name": "",
            "drk_price": 0,
            "drk_guid": "",
            "popup": "",
            "notice": "",
            "arc_type": 0,
            "drk_type": 0,
            "main_type": 0,
            "state": 1,
        },
    }


def test_fetch_item_posts_form_to_endpoint() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert str(request.url) == fetch_menu.FETCH_URL
        params = dict(parse_qsl(request.content.decode("utf-8")))
        assert params["sid"] == "42"
        assert params["id"] == "0007"
        assert params["tno"] == fetch_menu.DEFAULT_TABLE_NO
        assert params["num"] == fetch_menu.DEFAULT_PEOPLE_COUNT
        assert params["lng"] == fetch_menu.DEFAULT_LANGUAGE
        assert request.headers["x-requested-with"] == "XMLHttpRequest"
        return httpx.Response(200, json=_item_payload("0007"))

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http:
        result = fetch_menu.fetch_item("42", 7, http=http)
    assert result["item_data"]["id"] == "0007"
    assert len(seen) == 1


def test_crawl_writes_only_found_items_and_resumes(tmp_path: Path) -> None:
    out = tmp_path / "menu.json"

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(parse_qsl(request.content.decode("utf-8")))
        item_id = params["id"]
        if item_id == "0001":
            return httpx.Response(200, json=_item_payload("0001"))
        return httpx.Response(200, json={"result": "NG"})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http:
        results = fetch_menu.crawl(
            shops=["42"],
            out=out,
            item_code_count=3,
            shuffle=False,
            http=http,
        )

    assert "42" in results
    assert list(results["42"].keys()) == ["0001"]
    assert out.exists()
    persisted = json.loads(out.read_text(encoding="utf-8"))
    assert persisted == results

    calls: list[str] = []

    def second_handler(request: httpx.Request) -> httpx.Response:
        params = dict(parse_qsl(request.content.decode("utf-8")))
        calls.append(params["id"])
        return httpx.Response(200, json={"result": "NG"})

    transport2 = httpx.MockTransport(second_handler)
    with httpx.Client(transport=transport2) as http:
        fetch_menu.crawl(
            shops=["42"],
            out=out,
            item_code_count=3,
            shuffle=False,
            http=http,
        )
    assert "0001" not in calls
    assert sorted(calls) == ["0000", "0002"]
