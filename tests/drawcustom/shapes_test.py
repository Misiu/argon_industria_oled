"""Tests for polygon, circle, ellipse, arc, pieslice, percentage coordinates and anchor."""

from __future__ import annotations

from PIL import Image, ImageChops, ImageDraw

from tests.drawcustom.helpers import (
    ArgonOledDevice,
    draw_element,
    make_device,
    region_has_white,
    region_is_black,
)

# ---------------------------------------------------------------------------
# polygon
# ---------------------------------------------------------------------------


def test_polygon_outline_default(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """polygon draws a white outline triangle."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {"type": "polygon", "points": [10, 5, 60, 5, 35, 35]},
    )
    assert region_has_white(image, 10, 5, 60, 35)


def test_polygon_filled(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """polygon with fill=True fills the interior."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {"type": "polygon", "points": [10, 10, 60, 10, 60, 40, 10, 40], "fill": True},
    )
    assert region_has_white(image, 15, 15, 55, 35)


def test_polygon_list_of_pairs(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """polygon accepts points as a list of [x, y] pairs."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {"type": "polygon", "points": [[5, 5], [50, 5], [50, 30], [5, 30]]},
    )
    assert region_has_white(image, 5, 5, 50, 5)


def test_polygon_too_few_points_is_no_op(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """polygon with fewer than 2 points (flat list < 4) does nothing."""
    image, draw = black_canvas
    draw_element(device, image, draw, {"type": "polygon", "points": [5, 5]})
    assert region_is_black(image, 0, 0, 127, 63)


# ---------------------------------------------------------------------------
# circle
# ---------------------------------------------------------------------------


def test_circle_outline_default(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """circle draws a white outline circle."""
    image, draw = black_canvas
    draw_element(device, image, draw, {"type": "circle", "x": 40, "y": 32, "radius": 15})
    assert region_has_white(image, 25, 17, 55, 47)


def test_circle_filled(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """circle with fill=True fills the interior."""
    image, draw = black_canvas
    draw_element(
        device, image, draw, {"type": "circle", "x": 40, "y": 32, "radius": 15, "fill": True}
    )
    assert region_has_white(image, 30, 22, 50, 42)


def test_circle_percentage_radius(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """circle radius accepts a percentage string."""
    image, draw = black_canvas
    # 25% of min(128, 64) = 25% of 64 = 16 px
    draw_element(
        device, image, draw, {"type": "circle", "x": 64, "y": 32, "radius": "25%", "fill": True}
    )
    assert region_has_white(image, 50, 18, 78, 46)


# ---------------------------------------------------------------------------
# ellipse
# ---------------------------------------------------------------------------


def test_ellipse_outline_default(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """ellipse draws a white outline ellipse within its bounding box."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {"type": "ellipse", "x_start": 10, "y_start": 10, "x_end": 80, "y_end": 50},
    )
    assert region_has_white(image, 10, 29, 80, 31)  # midpoint of left/right arcs


def test_ellipse_filled(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """ellipse with fill=True fills the interior."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {
            "type": "ellipse",
            "x_start": 10,
            "y_start": 10,
            "x_end": 80,
            "y_end": 50,
            "fill": True,
        },
    )
    assert region_has_white(image, 20, 20, 70, 40)


def test_ellipse_percentage_coords(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """ellipse bounding box accepts percentage strings for all coordinates."""
    image, draw = black_canvas
    # 10%W=round(12.8)=13, 10%H=round(6.4)=6, 90%W=round(115.2)=115, 90%H=round(57.6)=58
    draw_element(
        device,
        image,
        draw,
        {
            "type": "ellipse",
            "x_start": "10%",
            "y_start": "10%",
            "x_end": "90%",
            "y_end": "90%",
            "fill": True,
        },
    )
    assert region_has_white(image, 30, 20, 100, 44)


# ---------------------------------------------------------------------------
# arc
# ---------------------------------------------------------------------------


def test_arc_draws_curve(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """arc draws a curved white line."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {
            "type": "arc",
            "x_start": 10,
            "y_start": 5,
            "x_end": 80,
            "y_end": 55,
            "start": 0,
            "end": 180,
        },
    )
    assert region_has_white(image, 10, 5, 80, 55)


def test_arc_percentage_angles(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """arc accepts percentage strings for start/end angles (% of 360°)."""
    image, draw = black_canvas
    # start=0%, end=50% → 0° to 180°
    draw_element(
        device,
        image,
        draw,
        {
            "type": "arc",
            "x_start": 10,
            "y_start": 5,
            "x_end": 80,
            "y_end": 55,
            "start": "0%",
            "end": "50%",
        },
    )
    assert region_has_white(image, 10, 5, 80, 55)


# ---------------------------------------------------------------------------
# pieslice
# ---------------------------------------------------------------------------


def test_pieslice_outline(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """pieslice draws white lines for the two radii and the arc."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {
            "type": "pieslice",
            "x_start": 10,
            "y_start": 5,
            "x_end": 80,
            "y_end": 55,
            "start": 0,
            "end": 180,
        },
    )
    assert region_has_white(image, 10, 5, 80, 55)


def test_pieslice_filled(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """pieslice with fill=True fills the slice interior."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {
            "type": "pieslice",
            "x_start": 10,
            "y_start": 5,
            "x_end": 80,
            "y_end": 55,
            "start": 0,
            "end": 180,
            "fill": True,
        },
    )
    assert region_has_white(image, 20, 10, 70, 30)


# ---------------------------------------------------------------------------
# Percentage coordinate support (shared across types)
# ---------------------------------------------------------------------------


def test_percentage_x_coordinate(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """x='50%' resolves to pixel 64 (50% of display width 128)."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {"type": "line", "x_start": "50%", "y_start": 0, "x_end": "50%", "y_end": 63},
    )
    assert region_has_white(image, 64, 0, 64, 63)


def test_percentage_y_coordinate(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """y='50%' resolves to pixel 32 (50% of display height 64)."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {"type": "line", "x_start": 0, "y_start": "50%", "x_end": 127, "y_end": "50%"},
    )
    assert region_has_white(image, 0, 32, 127, 32)


def test_percentage_pixel_element(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """pixel element accepts percentage strings for x and y."""
    image, draw = black_canvas
    draw_element(device, image, draw, {"type": "pixel", "x": "50%", "y": "50%"})
    assert image.getpixel((64, 32)) == 1


# ---------------------------------------------------------------------------
# Anchor support for text
# ---------------------------------------------------------------------------


def test_text_anchor_center(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """anchor='center' centres the text glyph around (x, y)."""
    cx, cy = 64, 32
    image_default, draw_default = black_canvas

    # Without anchor the text starts at top-left of (cx, cy)
    draw_element(
        device,
        image_default,
        draw_default,
        {"type": "text", "value": "X", "x": cx, "y": cy, "size": 10},
    )

    image_center = Image.new("1", (128, 64), color=0)
    draw_center = ImageDraw.Draw(image_center)
    dev2 = make_device()
    draw_element(
        dev2,
        image_center,
        draw_center,
        {"type": "text", "value": "X", "x": cx, "y": cy, "size": 10, "anchor": "center"},
    )

    # The two images must differ (anchor shifts the glyph position)
    diff = ImageChops.difference(image_default, image_center)
    assert diff.getbbox() is not None, "anchor=center should shift glyph position"
    # Both must contain white pixels around the centre
    assert region_has_white(image_center, 50, 20, 80, 44)


def test_text_anchor_aliases(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """'mm' and 'center' aliases resolve to the same Pillow anchor."""
    image_mm = black_canvas[0]
    draw_mm = black_canvas[1]
    draw_element(
        device,
        image_mm,
        draw_mm,
        {"type": "text", "value": "A", "x": 64, "y": 32, "size": 10, "anchor": "mm"},
    )

    image_center = Image.new("1", (128, 64), color=0)
    draw_center = ImageDraw.Draw(image_center)
    dev2 = make_device()
    draw_element(
        dev2,
        image_center,
        draw_center,
        {"type": "text", "value": "A", "x": 64, "y": 32, "size": 10, "anchor": "center"},
    )

    diff = ImageChops.difference(image_mm, image_center)
    assert diff.getbbox() is None, "'mm' and 'center' should produce identical output"
