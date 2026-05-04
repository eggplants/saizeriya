from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.update_shops import deduplicate, parse_page, render_module  # noqa: E402

SAMPLE_HTML = """
<html><body>
<table>
  <tr><td>
    <a href="//shop.saizeriya.co.jp/sz_restaurant/spot/detail?code=0004"
       onclick="gaTrackEvent(...);" target="_self">
        サイゼリヤ 平塚四宮店
    </a>
  </td></tr>
  <tr><td>
    <a href="//shop.saizeriya.co.jp/sz_restaurant/spot/detail?code=0005">
        サイゼリヤ　市川インター店
    </a>
  </td></tr>
  <tr><td>
    <a href="//shop.saizeriya.co.jp/sz_restaurant/spot/detail?code=99999">
        サイゼリヤ神奈川工場
    </a>
  </td></tr>
</table>
</body></html>
"""


def test_parse_page_extracts_code_and_name() -> None:
    pairs = parse_page(SAMPLE_HTML)
    assert pairs == [
        ("サイゼリヤ 平塚四宮店", "0004"),
        ("サイゼリヤ 市川インター店", "0005"),
        ("サイゼリヤ神奈川工場", "99999"),
    ]


def test_deduplicate_keeps_first_occurrence_for_same_code() -> None:
    pairs = [("A", "0001"), ("A", "0001"), ("B", "0002")]
    assert deduplicate(pairs) == {"A": "0001", "B": "0002"}


def test_deduplicate_warns_and_drops_conflicting_codes(capsys) -> None:  # type: ignore[no-untyped-def]
    pairs = [("X", "0001"), ("X", "0002")]
    result = deduplicate(pairs)
    assert result == {"X": "0001"}
    err = capsys.readouterr().err
    assert "duplicate" in err
    assert "X" in err


def test_render_module_is_sorted_by_code_and_double_quoted() -> None:
    text = render_module({"店舗B": "0010", "店舗A": "0005"})
    lines = text.splitlines()
    assert "SHOPS: dict[str, str] = {" in lines
    body = [line for line in lines if line.startswith("    ")]
    assert body == [
        '    "店舗A": "0005",',
        '    "店舗B": "0010",',
    ]
