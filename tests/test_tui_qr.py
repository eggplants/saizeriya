from __future__ import annotations

from pathlib import Path

import pytest
import zxingcpp
from PIL import Image

from saizeriya.tui.qr import QRDecodeError, decode_qr_texts, is_image_file, read_qr_url


def write_qr(path: Path, text: str) -> Path:
    barcode = zxingcpp.create_barcode(text, zxingcpp.BarcodeFormat.QRCode)
    image = zxingcpp.write_barcode_to_image(barcode, scale=6)
    height, width = image.shape[0], image.shape[1]
    Image.frombuffer("L", (width, height), bytes(memoryview(image))).save(path)
    return path


def test_is_image_file() -> None:
    assert is_image_file(Path("photo.PNG"))
    assert is_image_file(Path("shot.jpeg"))
    assert not is_image_file(Path("notes.txt"))
    assert not is_image_file(Path("no-suffix"))


def test_reads_a_saizeriya_qr_url(tmp_path: Path) -> None:
    url = "https://ioes.saizeriya.co.jp/saizeriya3/qr?t=51"
    path = write_qr(tmp_path / "qr.png", url)

    assert decode_qr_texts(path) == [url]
    assert read_qr_url(path) == url


def test_falls_back_to_any_http_payload(tmp_path: Path) -> None:
    url = "http://127.0.0.1:8000/mock/qr?table=1"
    path = write_qr(tmp_path / "qr.png", url)

    assert read_qr_url(path) == url


def test_rejects_a_qr_code_that_is_not_a_url(tmp_path: Path) -> None:
    path = write_qr(tmp_path / "qr.png", "ただのテキスト")

    with pytest.raises(QRDecodeError, match="URL ではありません"):
        read_qr_url(path)


def test_rejects_an_image_without_a_qr_code(tmp_path: Path) -> None:
    path = tmp_path / "blank.png"
    Image.new("RGB", (120, 120), "white").save(path)

    with pytest.raises(QRDecodeError, match="QR コードが見つかりません"):
        read_qr_url(path)


def test_rejects_a_file_that_is_not_an_image(tmp_path: Path) -> None:
    path = tmp_path / "notes.png"
    path.write_text("not an image", encoding="utf-8")

    with pytest.raises(QRDecodeError, match="画像として読み込めません"):
        read_qr_url(path)
