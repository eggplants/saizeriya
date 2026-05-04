from __future__ import annotations

import pytest

from saizeriya.page_parser import PageParser

MENU_HTML = """
<!doctype html><html><body>
<form id="frm_ctrl" class="page-base menu-page" action="./?abc123">
  <input id="shop-id" value="42">
  <input id="table-no" value="7">
  <input id="number" value="3">
  <input id="session-id" value="SID">
  <input name="token" value="TKN">
</form>
</body></html>
"""

TOP_HTML = """
<!doctype html><html><body>
<form id="frm_ctrl" class="top-page" action="/?xyz">
  <input id="shop-id" value="1">
  <input id="table-no" value="2">
</form>
<div id="number">2 名様</div>
</body></html>
"""

ACCOUNT_HTML = """
<!doctype html><html><body>
<form id="frm_ctrl" class="account-page" action="/?aid">
  <input id="shop-id" value="1">
  <input id="table-no" value="2">
</form>
<!-- [control_no] => CTRL01 -->
<!-- [dummy_no] => DUM02 -->
<div id="body-section">
  <div class="list-base">
    <table><tbody>
      <tr><td>ｴﾋﾞｻﾗﾀﾞ</td><td>2</td><td>700</td></tr>
      <tr><td>ﾃｨﾗﾐｽ</td><td>1</td><td>300</td></tr>
    </tbody></table>
  </div>
  <div class="amount">
    <div class="count"><span>3</span></div>
    <div class="amount"><span>1,000</span></div>
  </div>
</div>
</body></html>
"""

RECEIPT_HTML = """
<!doctype html><html><body>
<form id="frm_ctrl" class="receipt-page" action="/?rid">
  <input id="shop-id" value="1">
  <input id="table-no" value="2">
</form>
<div class="receipt-page">
  <div class="barcode">
    <img src="data:image/png;base64,AAAA">
    <p>1234 5678 9012</p>
  </div>
</div>
</body></html>
"""


def test_menu_page_basic_fields() -> None:
    parser = PageParser(MENU_HTML)
    assert parser.get_shop_id() == 42
    assert parser.get_table_no() == 7
    assert parser.get_people_count() == 3
    assert parser.get_session_id() == "SID"
    assert parser.get_token() == "TKN"
    assert parser.get_page_kind() == "menu"
    assert parser.get_next_action_id() == "abc123"


def test_top_page_people_count_from_label() -> None:
    parser = PageParser(TOP_HTML)
    assert parser.get_page_kind() == "top"
    assert parser.get_people_count() == 2
    assert parser.get_token() is None


def test_unknown_when_form_missing() -> None:
    parser = PageParser("<html><body><div /></body></html>")
    assert parser.get_page_kind() == "unknown"
    with pytest.raises(TypeError, match="frm_ctrl"):
        parser.get_next_action_id()


def test_account_summary() -> None:
    parser = PageParser(ACCOUNT_HTML)
    summary = parser.get_account_summary()
    assert summary.control_no == "CTRL01"
    assert summary.dummy_no == "DUM02"
    assert summary.count == 3
    assert summary.total == 1000
    assert summary.lines[0].name == "ｴﾋﾞｻﾗﾀﾞ"
    assert summary.lines[0].count == 2
    assert summary.lines[0].price == 700
    assert summary.lines[1].name == "ﾃｨﾗﾐｽ"


def test_receipt_summary() -> None:
    parser = PageParser(RECEIPT_HTML)
    summary = parser.get_receipt_summary()
    assert summary.barcode_value == "123456789012"
    assert summary.barcode_image_src == "data:image/png;base64,AAAA"
