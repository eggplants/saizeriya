from __future__ import annotations

import re

from urllib.parse import parse_qsl

from saizeriya.forms import (
    create_base_fields,
    create_order_submit_body,
    now_order_time,
    to_form_pairs,
)
from saizeriya.types import CartItem


def test_now_order_time_format() -> None:
    value = now_order_time()
    assert re.fullmatch(r"\d{4}/\d{2}/\d{2},\d{2}:\d{2}:\d{2}", value)


def test_create_base_fields_omits_token_when_absent() -> None:
    assert create_base_fields("menu") == {
        "proc": "menu",
        "ctrl": "",
        "sub_ctrl": "",
        "cur_lang": "1",
        "message": "",
    }


def test_create_base_fields_includes_token() -> None:
    fields = create_base_fields("main", "abc")
    assert fields["token"] == "abc"
    assert fields["proc"] == "main"


def test_to_form_pairs_drops_none_and_lowercases_bool() -> None:
    pairs = to_form_pairs({"a": 1, "b": True, "c": False, "d": "x", "e": None})
    assert pairs == [("a", "1"), ("b", "true"), ("c", "false"), ("d", "x")]


def test_create_order_submit_body_appends_array_fields() -> None:
    cart = [
        CartItem(id="1202", count=2, reorder=0, mod_id="", mod_count=0, name="x", price=350),
        CartItem(id="3201", count=1, reorder=1, mod_id="MX", mod_count=3),
    ]
    body = create_order_submit_body("tok", cart)
    pairs = parse_qsl(body.decode("utf-8"), keep_blank_values=True)

    assert ("token", "tok") in pairs
    assert ("ctrl", "remember") in pairs

    item_ids = [v for k, v in pairs if k == "item[id][]"]
    item_counts = [v for k, v in pairs if k == "item[count][]"]
    item_reorders = [v for k, v in pairs if k == "item[reorder][]"]
    item_mod_ids = [v for k, v in pairs if k == "item[mod_id][]"]
    item_mod_counts = [v for k, v in pairs if k == "item[mod_count][]"]

    assert item_ids == ["1202", "3201"]
    assert item_counts == ["2", "1"]
    assert item_reorders == ["0", "1"]
    assert item_mod_ids == ["", "MX"]
    assert item_mod_counts == ["0", "3"]
