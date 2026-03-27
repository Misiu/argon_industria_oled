"""Tests for the ``pixel`` element type color support."""

from __future__ import annotations

from PIL import Image, ImageDraw

from tests.drawcustom.helpers import (
    ArgonOledDevice,
    draw_element,
    make_device,
)


def test_pixel_white_default(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """Pixel without explicit color is drawn white (1)."""
    image, draw = black_canvas
    draw_element(device, image, draw, {"type": "pixel", "x": 10, "y": 10})
    assert image.getpixel((10, 10)) == 1


def test_pixel_white_explicit(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """Pixel with color=white is drawn white (1)."""
    image, draw = black_canvas
    draw_element(device, image, draw, {"type": "pixel", "x": 10, "y": 10, "color": "white"})
    assert image.getpixel((10, 10)) == 1


def test_pixel_black_on_black_canvas(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """Pixel with color=black on a black canvas stays 0."""
    image, draw = black_canvas
    draw_element(device, image, draw, {"type": "pixel", "x": 10, "y": 10, "color": "black"})
    assert image.getpixel((10, 10)) == 0


def test_pixel_black_clears_white_canvas(
    white_canvas: tuple[Image.Image, ImageDraw.ImageDraw],
) -> None:
    """Drawing a black pixel on a white canvas clears that pixel to 0."""
    image, draw = white_canvas
    dev = make_device()
    draw_element(dev, image, draw, {"type": "pixel", "x": 5, "y": 5, "color": "black"})
    assert image.getpixel((5, 5)) == 0
