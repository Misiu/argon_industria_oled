"""Tests for the ``rectangle`` and ``filled_rectangle`` element types."""

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

# ---------------------------------------------------------------------------
# filled_rectangle
# ---------------------------------------------------------------------------


def test_filled_rectangle_white_default(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """filled_rectangle without explicit color fills with white."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {"type": "filled_rectangle", "x_start": 10, "y_start": 10, "x_end": 40, "y_end": 30},
    )
    assert region_has_white(image, 11, 11, 39, 29)


def test_filled_rectangle_white_explicit(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """filled_rectangle with color=white fills with white."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {
            "type": "filled_rectangle",
            "x_start": 10,
            "y_start": 10,
            "x_end": 40,
            "y_end": 30,
            "color": "white",
        },
    )
    assert region_has_white(image, 11, 11, 39, 29)


def test_filled_rectangle_black_clears_area(
    white_canvas: tuple[Image.Image, ImageDraw.ImageDraw],
) -> None:
    """filled_rectangle with color=black clears the filled area on a white canvas."""
    before, _ = white_canvas
    after = before.copy()
    dev = make_device()
    draw_element(
        dev,
        after,
        ImageDraw.Draw(after),
        {
            "type": "filled_rectangle",
            "x_start": 10,
            "y_start": 10,
            "x_end": 40,
            "y_end": 30,
            "color": "black",
        },
    )
    assert region_changed(before, after, 10, 10, 40, 30)
    assert region_is_black(after, 11, 11, 39, 29)


def test_filled_rectangle_no_outline(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """outline=False does not prevent the fill from being drawn."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {
            "type": "filled_rectangle",
            "x_start": 20,
            "y_start": 20,
            "x_end": 60,
            "y_end": 50,
            "outline": False,
            "color": "white",
        },
    )
    assert region_has_white(image, 21, 21, 59, 49)


# ---------------------------------------------------------------------------
# rectangle (outline only)
# ---------------------------------------------------------------------------


def test_rectangle_white_default(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """rectangle without explicit color draws a white outline."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {"type": "rectangle", "x_start": 5, "y_start": 5, "x_end": 50, "y_end": 40},
    )
    assert region_has_white(image, 5, 5, 50, 5)


def test_rectangle_black_outline_on_black_canvas(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """rectangle with color=black does not set any pixels on a black canvas."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {
            "type": "rectangle",
            "x_start": 5,
            "y_start": 5,
            "x_end": 50,
            "y_end": 40,
            "color": "black",
        },
    )
    assert region_is_black(image, 5, 5, 50, 40)


def test_rectangle_with_fill(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """fill=True fills the interior with the element color."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {
            "type": "rectangle",
            "x_start": 5,
            "y_start": 5,
            "x_end": 50,
            "y_end": 40,
            "fill": True,
            "color": "white",
        },
    )
    assert region_has_white(image, 10, 10, 45, 35)


def test_rectangle_no_fill_leaves_interior_unchanged(
    white_canvas: tuple[Image.Image, ImageDraw.ImageDraw],
) -> None:
    """fill=False (default) does not modify the interior pixels."""
    before, _ = white_canvas
    after = before.copy()
    dev = make_device()
    draw_element(
        dev,
        after,
        ImageDraw.Draw(after),
        {"type": "rectangle", "x_start": 10, "y_start": 10, "x_end": 50, "y_end": 40},
    )
    # Interior should still be white (untouched)
    assert region_has_white(after, 15, 15, 45, 35)
