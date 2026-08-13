"""Decode Saizeriya QR codes from local image files.

There is no camera in a terminal, so the TUI reads the QR code out of an image
the user picks from disk (a screenshot or a photo of the in-store table card).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from saizeriya.tui import missing_dependency_message

if TYPE_CHECKING:
    from pathlib import Path

IMAGE_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".ppm", ".pgm"},
)

SAIZERIYA_MARKER = "saizeriya"


class QRDecodeError(Exception):
    """Raised when no usable QR code could be read from an image."""


def is_image_file(path: Path) -> bool:
    """Return whether the path looks like a readable image by extension."""
    return path.suffix.lower() in IMAGE_SUFFIXES


def decode_qr_texts(path: Path) -> list[str]:
    """Return every QR/barcode payload found in the image at `path`."""
    try:
        import zxingcpp  # noqa: PLC0415
        from PIL import Image, UnidentifiedImageError  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - depends on install extras
        msg = f"{missing_dependency_message(exc.name)}。URL を直接入力してください"
        raise QRDecodeError(msg) from exc

    try:
        with Image.open(path) as image:
            results = zxingcpp.read_barcodes(image.convert("L"))
    except (UnidentifiedImageError, OSError) as exc:
        msg = f"画像として読み込めませんでした: {path}"
        raise QRDecodeError(msg) from exc

    return [result.text for result in results if result.text]


def read_qr_url(path: Path) -> str:
    """Return the Saizeriya QR URL contained in the image at `path`.

    Prefers a payload that mentions Saizeriya, mirroring the web client's guard;
    falls back to the first `http(s)` payload so mock-server QR codes also work.
    """
    texts = decode_qr_texts(path)
    if not texts:
        msg = f"QR コードが見つかりませんでした: {path.name}"
        raise QRDecodeError(msg)

    for text in texts:
        if SAIZERIYA_MARKER in text.lower():
            return text

    for text in texts:
        if text.lower().startswith(("http://", "https://")):
            return text

    msg = f"QR コードは読めましたが URL ではありませんでした: {texts[0][:60]}"
    raise QRDecodeError(msg)
