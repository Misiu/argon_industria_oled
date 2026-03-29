"""Tests for the ``progress_bar`` element type."""

from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from tests.drawcustom.helpers import (
    ArgonOledDevice,
    DeviceError,
    draw_element,
    region_changed,
    region_has_white,
    region_is_black,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BAR = {"type": "progress_bar", "x_start": 10, "y_start": 10, "x_end": 90, "y_end": 30}


def _draw(
    element: dict,
    canvas: tuple[Image.Image, ImageDraw.ImageDraw] | None = None,
) -> Image.Image:
    """Draw *element* on a fresh black canvas and return the image."""
    if canvas is None:
        image = Image.new("1", (128, 64), color=0)
        draw = ImageDraw.Draw(image)
    else:
        image, draw = canvas
    dev: ArgonOledDevice = object.__new__(ArgonOledDevice)
    dev._state = None  # pylint: disable=protected-access
    draw_element(dev, image, draw, element)
    return image


# ---------------------------------------------------------------------------
# Direction: right (default)
# ---------------------------------------------------------------------------


def test_progress_bar_right_fills_left_portion(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """50 % right-direction bar fills the left half of the bar interior."""
    image, draw = black_canvas
    # bar_w = 90-10 = 80; filled_w = int(80*50/100) = 40 → fill x: 10..50
    draw_element(device, image, draw, {**_BAR, "progress": 50})
    assert region_has_white(image, 11, 11, 49, 29)  # inside fill zone
    assert region_is_black(image, 52, 11, 88, 29)  # inside unfilled zone


def test_progress_bar_right_full(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """100 % progress fills the entire bar interior."""
    image, draw = black_canvas
    draw_element(device, image, draw, {**_BAR, "progress": 100})
    assert region_has_white(image, 11, 11, 89, 29)


def test_progress_bar_right_zero(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """0 % progress leaves the bar interior black (outline=black too)."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {**_BAR, "progress": 0, "outline": "black"},
    )
    assert region_is_black(image, 11, 11, 89, 29)


# ---------------------------------------------------------------------------
# Direction: left
# ---------------------------------------------------------------------------


def test_progress_bar_left_fills_right_portion(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """50 % left-direction bar fills the right half of the bar interior."""
    image, draw = black_canvas
    # filled_w = 40 → fill x: (90-40)=50..90
    draw_element(device, image, draw, {**_BAR, "progress": 50, "direction": "left"})
    assert region_has_white(image, 51, 11, 89, 29)  # inside fill zone
    assert region_is_black(image, 12, 11, 48, 29)  # inside unfilled zone


# ---------------------------------------------------------------------------
# Direction: down
# ---------------------------------------------------------------------------


def test_progress_bar_down_fills_top_portion(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """50 % down-direction bar fills the top half of the bar interior."""
    # Taller bar so the height arithmetic is clear
    bar = {"type": "progress_bar", "x_start": 10, "y_start": 10, "x_end": 90, "y_end": 60}
    image, draw = black_canvas
    # bar_h = 50; filled_h = 25 → fill y: 10..35
    draw_element(device, image, draw, {**bar, "progress": 50, "direction": "down"})
    assert region_has_white(image, 11, 11, 89, 34)  # inside fill zone
    assert region_is_black(image, 11, 37, 89, 59)  # inside unfilled zone


# ---------------------------------------------------------------------------
# Direction: up
# ---------------------------------------------------------------------------


def test_progress_bar_up_fills_bottom_portion(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """50 % up-direction bar fills the bottom half of the bar interior."""
    bar = {"type": "progress_bar", "x_start": 10, "y_start": 10, "x_end": 90, "y_end": 60}
    image, draw = black_canvas
    # bar_h = 50; filled_h = 25 → fill y: (60-25)=35..60
    draw_element(device, image, draw, {**bar, "progress": 50, "direction": "up"})
    assert region_has_white(image, 11, 36, 89, 59)  # inside fill zone
    assert region_is_black(image, 11, 12, 89, 33)  # inside unfilled zone


# ---------------------------------------------------------------------------
# Progress clamping
# ---------------------------------------------------------------------------


def test_progress_bar_clamped_above_100(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """Progress values above 100 are treated as 100 (full bar)."""
    image, draw = black_canvas
    draw_element(device, image, draw, {**_BAR, "progress": 999})
    assert region_has_white(image, 11, 11, 89, 29)


def test_progress_bar_clamped_below_0(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """Progress values below 0 are treated as 0 (empty bar, outline=black)."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {**_BAR, "progress": -50, "outline": "black"},
    )
    assert region_is_black(image, 11, 11, 89, 29)


# ---------------------------------------------------------------------------
# Outline
# ---------------------------------------------------------------------------


def test_progress_bar_outline_drawn(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """Default outline (white) is rendered on the bar border."""
    image, draw = black_canvas
    draw_element(device, image, draw, {**_BAR, "progress": 0})
    # Top border of the outline must contain white pixels
    assert region_has_white(image, 10, 10, 90, 10)


def test_progress_bar_outline_black_no_border(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """outline=black on a black canvas leaves no pixels set on the border."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {**_BAR, "progress": 0, "outline": "black"},
    )
    assert region_is_black(image, 10, 10, 90, 30)


# ---------------------------------------------------------------------------
# Background color
# ---------------------------------------------------------------------------


def test_progress_bar_background_white(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """background=white fills the whole bar area even at 0 % progress."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {**_BAR, "progress": 0, "background": "white", "outline": "black"},
    )
    assert region_has_white(image, 11, 11, 89, 29)


# ---------------------------------------------------------------------------
# Fill color
# ---------------------------------------------------------------------------


def test_progress_bar_fill_black_on_white_background(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """fill=black on a white background clears the filled region."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {
            **_BAR,
            "progress": 50,
            "background": "white",
            "fill": "black",
            "outline": "white",
        },
    )
    # Interior of the fill region must be black (fill erases white background)
    assert region_is_black(image, 12, 11, 48, 29)
    # Interior of the unfilled region stays white (background)
    assert region_has_white(image, 52, 11, 88, 29)


# ---------------------------------------------------------------------------
# show_percentage — XOR compositing
# ---------------------------------------------------------------------------


def test_progress_bar_show_percentage_xor_on_white_fill() -> None:
    """Text pixels over white (filled) region invert to black — XOR effect.

    With plain "draw white text" the label would be invisible against a white
    fill. The XOR composite flips those pixels to black, so a change is
    detectable by comparing images drawn with and without show_percentage.
    """
    bar = {
        "type": "progress_bar",
        "x_start": 0,
        "y_start": 0,
        "x_end": 127,
        "y_end": 63,
        "progress": 100,  # fully filled → interior is all white
        "fill": "white",
        "outline": "black",
        "background": "white",
        "size": 16,
    }
    image_no_text = _draw({**bar, "show_percentage": False})
    image_with_text = _draw({**bar, "show_percentage": True})
    # XOR turned text pixels from white → black; the region around the
    # centre must have changed.
    assert region_changed(image_no_text, image_with_text, 20, 15, 110, 50)


def test_progress_bar_show_percentage_xor_on_black_background() -> None:
    """Text pixels over black (unfilled) region invert to white — XOR effect.

    With plain "draw black text" the label would be invisible against a black
    background. The XOR composite flips those pixels to white.
    """
    bar = {
        "type": "progress_bar",
        "x_start": 0,
        "y_start": 0,
        "x_end": 127,
        "y_end": 63,
        "progress": 0,  # empty → interior is all black
        "fill": "white",
        "outline": "black",
        "background": "black",
        "size": 16,
    }
    image_no_text = _draw({**bar, "show_percentage": False})
    image_with_text = _draw({**bar, "show_percentage": True})
    # XOR turned text pixels from black → white; the centre region changed.
    assert region_changed(image_no_text, image_with_text, 20, 15, 110, 50)


def test_progress_bar_show_percentage_xor_splits_at_boundary() -> None:
    """At 50 % progress the label straddles fill and background.

    Text pixels over the white fill become black; text pixels over the black
    background become white.  Both halves must produce a visible change
    compared to the version without the label.
    """
    bar = {
        "type": "progress_bar",
        "x_start": 0,
        "y_start": 0,
        "x_end": 127,
        "y_end": 63,
        "progress": 50,
        "fill": "white",
        "outline": "black",
        "background": "black",
        "size": 16,
    }
    image_no_text = _draw({**bar, "show_percentage": False})
    image_with_text = _draw({**bar, "show_percentage": True})
    # The label "50%" is centred at x≈63 which sits right at the fill boundary.
    # Regardless of the exact glyph placement, the whole centre region must
    # differ between the two renders.
    assert region_changed(image_no_text, image_with_text, 20, 15, 110, 50)


def test_progress_bar_no_percentage_by_default(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """show_percentage defaults to False — no text pixels appear."""
    image, draw = black_canvas
    draw_element(
        device,
        image,
        draw,
        {
            **_BAR,
            "progress": 0,
            # Black everything so the canvas stays fully black
            "fill": "black",
            "outline": "black",
            "background": "black",
        },
    )
    assert region_is_black(image, 11, 11, 89, 29)


# ---------------------------------------------------------------------------
# Invalid direction
# ---------------------------------------------------------------------------


def test_progress_bar_invalid_direction_raises(
    device: ArgonOledDevice, black_canvas: tuple[Image.Image, ImageDraw.ImageDraw]
) -> None:
    """An unrecognised direction value raises DeviceError."""
    image, draw = black_canvas
    with pytest.raises(DeviceError):
        draw_element(
            device,
            image,
            draw,
            {**_BAR, "progress": 50, "direction": "diagonal"},
        )


# ---------------------------------------------------------------------------
# make_device path (covers the standalone helper)
# ---------------------------------------------------------------------------


def test_progress_bar_standalone_make_device() -> None:
    """make_device() path: progress bar draws correctly without fixtures."""
    image = _draw({**_BAR, "progress": 100})
    assert region_has_white(image, 11, 11, 89, 29)
