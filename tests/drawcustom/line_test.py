"""Tests for the ``line`` element type color support."""

from __future__ import annotations

from PIL import Image, ImageDraw

from tests.drawcustom.helpers import (
    ArgonOledDevice,
    draw_element,
    make_device,
    region_changed,
    region_has_white,
    region_is_black,
)


def test_line_white_default(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """Line without explicit color is drawn white."""
    image, draw = black_canvas
    draw_element(
        device, image, draw, {"type": "line", "x_start": 0, "y_start": 32, "x_end": 40, "y_end": 32}
    )
    assert region_has_white(image, 0, 32, 40, 32)


def test_line_white_explicit(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """Line with color=white is drawn white."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {"type": "line", "x_start": 0, "y_start": 32, "x_end": 40, "y_end": 32, "color": "white"},
    )
    assert region_has_white(image, 0, 32, 40, 32)


def test_line_black_on_black_canvas(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """Black line on a black canvas leaves all pixels at 0."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {"type": "line", "x_start": 0, "y_start": 32, "x_end": 40, "y_end": 32, "color": "black"},
    )
    assert region_is_black(image, 0, 32, 40, 32)


def test_line_black_erases_pixels(white_canvas: tuple[Image.Image, ImageDraw.ImageDraw]) -> None:
    """Black line on a white canvas clears pixels along the line."""
    before, _ = white_canvas
    after = before.copy()
    dev = make_device()
    draw_element(
        dev,
        after,
        ImageDraw.Draw(after),
        {"type": "line", "x_start": 0, "y_start": 10, "x_end": 50, "y_end": 10, "color": "black"},
    )
    assert region_changed(before, after, 0, 10, 50, 10)
    assert region_is_black(after, 0, 10, 50, 10)
