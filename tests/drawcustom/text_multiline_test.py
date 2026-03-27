"""Tests for the ``multiline`` element type color support."""

from __future__ import annotations

from PIL import Image, ImageDraw

from tests.drawcustom.helpers import (
    ArgonOledDevice,
    draw_element,
    make_device,
    region_changed,
    region_has_white,
)


def test_multiline_white_default(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """Multiline text without explicit color renders white glyphs."""
    image, draw = black_canvas
    draw_element(
        device, image, draw, {"type": "multiline", "x": 0, "y": 0, "value": "Hi|there", "size": 8}
    )
    assert region_has_white(image, 0, 0, 40, 30)


def test_multiline_white_explicit(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """Multiline text with color=white renders white glyphs."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {"type": "multiline", "x": 0, "y": 0, "value": "Hi|there", "size": 8, "color": "white"},
    )
    assert region_has_white(image, 0, 0, 40, 30)


def test_multiline_black_changes_pixels(
    white_canvas: tuple[Image.Image, ImageDraw.ImageDraw],
) -> None:
    """Black multiline text on a white canvas changes at least some pixels."""
    before, _ = white_canvas
    after = before.copy()
    dev = make_device()
    draw_element(
        dev,
        after,
        ImageDraw.Draw(after),
        {"type": "multiline", "x": 0, "y": 0, "value": "Hi|there", "size": 8, "color": "black"},
    )
    assert region_changed(before, after, 0, 0, 40, 30)


def test_multiline_delimiter(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """Custom delimiter splits text across lines."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {"type": "multiline", "x": 0, "y": 0, "value": "line1;line2", "size": 8, "delimiter": ";"},
    )
    assert region_has_white(image, 0, 0, 40, 30)
