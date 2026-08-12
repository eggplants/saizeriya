from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from saizeriya.menu import (
    MenuItem,
    default_menu,
    filter_menu_for_service_period,
    get_menu_service_period,
    is_alcohol_menu_item,
    load_menu,
    matches_menu_search,
    normalize_menu_search_text,
)

if TYPE_CHECKING:
    from pathlib import Path

JST = timezone(timedelta(hours=9))

SEARCH_ITEM = MenuItem(
    code="1202",
    name="小ｴﾋﾞのｻﾗﾀﾞ",
    kana="ｺｴﾋﾞﾉｻﾗﾀﾞ",
    price=350,
    category="サラダ",
    tags=["海老"],
)


def item(code: str, name: str, category: str, price: int = 400) -> MenuItem:
    return MenuItem(code=code, name=name, kana=name, price=price, category=category)


# --- seed data ---


def test_bundled_menu_loads() -> None:
    menu = default_menu()

    assert len(menu) > 100
    assert all(len(entry.code) == 4 and entry.code.isdigit() for entry in menu)
    assert all(entry.name for entry in menu)


def test_load_menu_skips_malformed_entries(tmp_path: Path) -> None:
    path = tmp_path / "menu.json"
    path.write_text(
        '[{"code": "1202", "name": "小ｴﾋﾞのｻﾗﾀﾞ", "price": 350, "category": "サラダ"},'
        '{"code": "12", "name": "bad"}, {"code": "1203", "name": "   "}]',
        encoding="utf-8",
    )

    menu = load_menu(path)

    assert [entry.code for entry in menu] == ["1202"]
    assert menu[0].kana == "小ｴﾋﾞのｻﾗﾀﾞ"


# --- search ---


def test_normalizes_half_width_and_full_width_characters() -> None:
    assert normalize_menu_search_text(" ＡＢＣ１２３ ｺｴﾋﾞ ") == "abc123コエビ"
    assert matches_menu_search(SEARCH_ITEM, "小エビ")
    assert matches_menu_search(SEARCH_ITEM, "ｺｴﾋﾞ")


def test_matches_menu_code_without_fuzzy_numeric_false_positives() -> None:
    assert matches_menu_search(SEARCH_ITEM, "120")
    assert not matches_menu_search(SEARCH_ITEM, "1203")


def test_matches_small_typos_with_fuzzy_search() -> None:
    assert matches_menu_search(SEARCH_ITEM, "小エビのサタダ")
    assert matches_menu_search(SEARCH_ITEM, "小エビサラ")


def test_requires_every_search_token_to_match() -> None:
    assert matches_menu_search(SEARCH_ITEM, "小エビ サラダ")
    assert not matches_menu_search(SEARCH_ITEM, "小エビ ドリア")


def test_empty_query_matches_everything() -> None:
    assert matches_menu_search(SEARCH_ITEM, "")
    assert matches_menu_search(SEARCH_ITEM, "   ")


# --- availability ---


def test_detects_weekday_lunch_before_15() -> None:
    assert get_menu_service_period(datetime(2026, 5, 4, 14, 59, tzinfo=JST)) == "lunch"
    assert get_menu_service_period(datetime(2026, 5, 4, 15, 0, tzinfo=JST)) == "regular"
    assert get_menu_service_period(datetime(2026, 5, 3, 12, 0, tzinfo=JST)) == "regular"


def test_service_period_is_evaluated_in_tokyo_time() -> None:
    # 2026-05-04 09:00 JST is still 2026-05-03 (Sunday) in UTC.
    assert get_menu_service_period(datetime(2026, 5, 4, 0, 0, tzinfo=UTC)) == "lunch"


def test_shows_both_lunch_and_regular_items_during_lunch() -> None:
    menu = [
        item("1135", "ﾗﾝﾁ)ﾀﾗｺｿｰｽｼｼﾘｰ風", "ランチ", 500),
        item("2301", "ﾀﾗｺｿｰｽｼｼﾘｰ風", "パスタ"),
        item("1202", "小ｴﾋﾞのｻﾗﾀﾞ", "サラダ", 350),
    ]

    assert [entry.code for entry in filter_menu_for_service_period(menu, "lunch")] == ["1135", "2301", "1202"]


def test_shows_regular_item_instead_of_lunch_item_outside_lunch() -> None:
    menu = [
        item("1135", "ﾗﾝﾁ)ﾀﾗｺｿｰｽｼｼﾘｰ風", "ランチ", 500),
        item("2301", "ﾀﾗｺｿｰｽｼｼﾘｰ風", "パスタ"),
    ]

    assert [entry.code for entry in filter_menu_for_service_period(menu, "regular")] == ["2301"]


def test_keeps_the_current_lunch_category_only_for_current_lunch_codes() -> None:
    menu = [
        item("1115", "ﾗﾝﾁ)ｽﾊﾟｹﾞｯﾃｨﾎﾟﾓﾄﾞｰﾛ", "ランチ", 500),
        item("1120", "ﾗﾝﾁ)ﾐｰﾄｿｰｽﾎﾞﾛﾆｱ風", "パスタ", 500),
        item("2307", "ｽﾊﾟｹﾞｯﾃｨﾎﾟﾓﾄﾞｰﾛ", "パスタ"),
    ]

    filtered = filter_menu_for_service_period(menu, "lunch")

    assert [entry.code for entry in filtered] == ["1120", "2307"]
    assert filtered[0].category == "ランチ"


def test_filtering_does_not_mutate_the_input() -> None:
    menu = [item("1120", "ﾗﾝﾁ)ﾐｰﾄｿｰｽﾎﾞﾛﾆｱ風", "パスタ", 500)]

    filter_menu_for_service_period(menu, "lunch")

    assert menu[0].category == "パスタ"


# --- classification ---


def alcohol_item(**kwargs: object) -> MenuItem:
    base = {
        "code": "9999",
        "name": "ミラノ風ドリア",
        "kana": "ミラノフウドリア",
        "price": 300,
        "category": "ドリア・グラタン",
        "tags": [],
    }
    base.update(kwargs)
    return MenuItem(**base)  # ty: ignore[invalid-argument-type]


def test_detects_saizeriya_wine_menu_items() -> None:
    assert is_alcohol_menu_item(alcohol_item(name="赤ｸﾞﾗｽﾜｲﾝ", category="ワイン"))
    assert is_alcohol_menu_item(alcohol_item(name="赤ﾃﾞｶﾝﾀ小", category="ワイン"))


def test_detects_alcohol_from_common_drink_names_and_tags() -> None:
    assert is_alcohol_menu_item(alcohol_item(name="生ビール", category="ドリンク"))
    assert is_alcohol_menu_item(alcohol_item(tags=["アルコール"]))


def test_detects_draft_beer_mug_and_frozen_alcohol_items() -> None:
    assert is_alcohol_menu_item(alcohol_item(name="中ジョッキ", category="ドリンク"))
    assert is_alcohol_menu_item(alcohol_item(name="氷結レモン", category="ドリンク"))


def test_does_not_classify_food_or_non_alcohol_drinks_as_alcohol() -> None:
    assert not is_alcohol_menu_item(alcohol_item())
    assert not is_alcohol_menu_item(alcohol_item(name="セットドリンクバー", category="ドリンク"))
    assert not is_alcohol_menu_item(alcohol_item(name="ノンアルコールビール", category="ドリンク"))


def test_uses_alcohol_check_field() -> None:
    assert is_alcohol_menu_item(alcohol_item(alcohol_check=1))
    assert not is_alcohol_menu_item(alcohol_item(alcohol_check=0))
    assert is_alcohol_menu_item(alcohol_item(name="生ビール", alcohol_check=1))
    assert not is_alcohol_menu_item(alcohol_item(name="ノンアルコールビール", alcohol_check=0))
