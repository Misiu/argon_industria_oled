"""Tests for the ``rectangle`` element type."""

from __future__ import annotations

from PIL import Image, ImageChops, ImageDraw

from tests.drawcustom.helpers import (
    ArgonOledDevice,
    draw_element,
    make_device,
    region_changed,
    region_has_white,
    region_is_black,
)

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


def test_rectangle_fill_black_clears_area(
    white_canvas: tuple[Image.Image, ImageDraw.ImageDraw],
) -> None:
    """rectangle with fill=True and color=black clears the filled area on a white canvas."""
    before, _ = white_canvas
    after = before.copy()
    dev = make_device()
    draw_element(
        dev,
        after,
        ImageDraw.Draw(after),
        {
            "type": "rectangle",
            "x_start": 10,
            "y_start": 10,
            "x_end": 40,
            "y_end": 30,
            "fill": True,
            "color": "black",
        },
    )
    assert region_changed(before, after, 10, 10, 40, 30)
    assert region_is_black(after, 11, 11, 39, 29)


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


def test_rectangle_width_thickens_outline(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """width > 1 draws a thicker outline that covers more pixels."""
    image1, draw1 = black_canvas
    draw_element(
        device,
        image1,
        draw1,
        {"type": "rectangle", "x_start": 10, "y_start": 10, "x_end": 60, "y_end": 50, "width": 1},
    )
    image3 = Image.new("1", (128, 64), color=0)
    draw3 = ImageDraw.Draw(image3)
    draw_element(
        device,
        image3,
        draw3,
        {"type": "rectangle", "x_start": 10, "y_start": 10, "x_end": 60, "y_end": 50, "width": 3},
    )
    # width=3 must light up pixels inside the border that width=1 left dark
    assert region_has_white(image3, 11, 11, 12, 12)


def test_rectangle_radius_rounds_corners(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """radius > 0 draws a rounded rectangle; corners are not filled."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {
            "type": "rectangle",
            "x_start": 10,
            "y_start": 10,
            "x_end": 60,
            "y_end": 50,
            "radius": 6,
        },
    )
    # Mid-point of each edge must be white (outline present)
    assert region_has_white(image, 30, 10, 40, 10)  # top edge midpoint
    assert region_has_white(image, 30, 50, 40, 50)  # bottom edge midpoint
    assert region_has_white(image, 10, 28, 10, 32)  # left edge midpoint
    assert region_has_white(image, 60, 28, 60, 32)  # right edge midpoint
    # Exact corners (before the arc) should be black (rounded away)
    assert region_is_black(image, 10, 10, 10, 10)
    assert region_is_black(image, 60, 10, 60, 10)
    assert region_is_black(image, 10, 50, 10, 50)
    assert region_is_black(image, 60, 50, 60, 50)


def test_rectangle_radius_with_fill(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """radius with fill=True fills the rounded rectangle interior."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {
            "type": "rectangle",
            "x_start": 10,
            "y_start": 10,
            "x_end": 60,
            "y_end": 50,
            "radius": 6,
            "fill": True,
        },
    )
    # Centre of the rectangle must be white (filled)
    assert region_has_white(image, 25, 20, 45, 40)


def test_rectangle_radius_zero_is_sharp(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """radius=0 (default) produces sharp corners identical to omitting radius."""
    image_no_radius, draw_no_radius = black_canvas
    draw_element(
        device,
        image_no_radius,
        draw_no_radius,
        {"type": "rectangle", "x_start": 10, "y_start": 10, "x_end": 60, "y_end": 50},
    )
    image_zero = Image.new("1", (128, 64), color=0)
    draw_zero = ImageDraw.Draw(image_zero)
    draw_element(
        device,
        image_zero,
        draw_zero,
        {
            "type": "rectangle",
            "x_start": 10,
            "y_start": 10,
            "x_end": 60,
            "y_end": 50,
            "radius": 0,
        },
    )
    diff = ImageChops.difference(image_no_radius, image_zero)
    assert diff.getbbox() is None, "radius=0 should produce identical output to no-radius"
