"""Module 10 tests (1+2): image upload validation & invalid-file rejection."""
from __future__ import annotations

import pytest

from app.services.reconstruct.validation import (
    UploadedFile,
    UploadValidationError,
    sniff_format,
    validate_image,
)

from .reconstruct_helpers import make_image

MAX = 10 * 1024 * 1024


def _ok(fmt: str, size=(320, 240)) -> UploadedFile:
    ext = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[fmt]
    return UploadedFile(f"boat{ext}", make_image(fmt, size))


# -- 1. upload validation ---------------------------------------------------
def test_accepts_real_jpeg():
    fmt, w, h = validate_image(_ok("JPEG"), max_bytes=MAX)
    assert fmt == "JPEG" and (w, h) == (320, 240)


def test_accepts_real_png():
    fmt, w, h = validate_image(_ok("PNG"), max_bytes=MAX)
    assert fmt == "PNG" and (w, h) == (320, 240)


def test_accepts_real_webp():
    fmt, w, h = validate_image(_ok("WEBP"), max_bytes=MAX)
    assert fmt == "WEBP" and (w, h) == (320, 240)


def test_sniff_rejects_non_image_bytes():
    assert sniff_format(b"hello, definitely not an image") is None
    assert sniff_format(b"") is None


def test_webp_magic_requires_riff_webp():
    # RIFF header with WEBP tag
    assert sniff_format(b"RIFF\x10\x00\x00\x00WEBPstuff") == "WEBP"
    # RIFF but NOT webp
    assert sniff_format(b"RIFF\x10\x00\x00\x00AVI stuff") is None


# -- 2. invalid file rejection ----------------------------------------------
def test_rejects_empty_file():
    with pytest.raises(UploadValidationError) as exc:
        validate_image(UploadedFile("boat.jpg", b""), max_bytes=MAX)
    assert "empty" in str(exc.value)


def test_rejects_oversized_file():
    big = b"\xff\xd8\xff" + b"\x00" * (MAX + 1)
    with pytest.raises(UploadValidationError) as exc:
        validate_image(UploadedFile("boat.jpg", big), max_bytes=MAX)
    assert "limit" in str(exc.value)


@pytest.mark.parametrize("name", ["boat.txt", "boat.gif", "boat", "boat.JPG.exe"])
def test_rejects_extension_mismatch(name):
    data = make_image("JPEG")
    with pytest.raises(UploadValidationError) as exc:
        validate_image(UploadedFile(name, data), max_bytes=MAX)
    assert "extension" in str(exc.value)


def test_rejects_corrupt_image_data():
    # real JPEG magic but truncated/garbage payload
    data = b"\xff\xd8\xff\xe0" + b"\x00" * 64
    with pytest.raises(UploadValidationError) as exc:
        validate_image(UploadedFile("boat.jpg", data), max_bytes=MAX)
    assert "decode" in str(exc.value)


def test_rejects_text_file_renamed_as_image():
    with pytest.raises(UploadValidationError) as exc:
        validate_image(UploadedFile("boat.jpg", b"plain text"), max_bytes=MAX)
    assert "magic" in str(exc.value)


def test_rejects_tiny_image():
    tiny = make_image("PNG", size=(4, 4))
    with pytest.raises(UploadValidationError) as exc:
        validate_image(UploadedFile("tiny.png", tiny), max_bytes=MAX)
    assert "too small" in str(exc.value)


def test_rejects_truncated_png():
    data = make_image("PNG")[:40]  # cut mid-stream
    with pytest.raises(UploadValidationError) as exc:
        validate_image(UploadedFile("boat.png", data), max_bytes=MAX)
    assert "decode" in str(exc.value)
