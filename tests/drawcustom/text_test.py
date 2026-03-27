"""Tests for the ``text`` element type color support."""

from __future__ import annotations

from PIL import Image, ImageChops, ImageDraw

from tests.drawcustom.helpers import (
    ArgonOledDevice,
    draw_element,
    make_device,
    region_changed,
    region_has_white,
)


def test_text_white_default(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """Text without explicit color renders white glyphs on a black canvas."""
    image, draw = black_canvas
    draw_element(device, image, draw, {"type": "text", "x": 0, "y": 0, "value": "A", "size": 10})
    assert region_has_white(image, 0, 0, 20, 15)


def test_text_white_explicit(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """Text with color=white renders white glyphs."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {"type": "text", "x": 0, "y": 0, "value": "A", "size": 10, "color": "white"},
    )
    assert region_has_white(image, 0, 0, 20, 15)


def test_text_black_changes_pixels(white_canvas: tuple[Image.Image, ImageDraw.ImageDraw]) -> None:
    """Black text on a white canvas changes at least some pixels."""
    before, _ = white_canvas
    after = before.copy()
    dev = make_device()
    draw_element(
        dev,
        after,
        ImageDraw.Draw(after),
        {"type": "text", "x": 0, "y": 0, "value": "A", "size": 10, "color": "black"},
    )
    assert region_changed(before, after, 0, 0, 30, 20)


def test_text_over_filled_rectangle(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """Drawing a white filled rectangle then black text over it changes the text area."""
    image, draw = black_canvas
    # Step 1: white filled rectangle
    draw_element(
        device,
        image,
        draw,
        {
            "type": "filled_rectangle",
            "x_start": 0,
            "y_start": 0,
            "x_end": 60,
            "y_end": 20,
            "color": "white",
        },
    )
    filled = image.copy()
    # Step 2: black text on top
    draw_element(
        device,
        image,
        draw,
        {"type": "text", "x": 2, "y": 2, "value": "Hi", "size": 10, "color": "black"},
    )
    diff = ImageChops.difference(filled, image)
    assert diff.getbbox() is not None, "Black text over white rectangle should change pixels"
