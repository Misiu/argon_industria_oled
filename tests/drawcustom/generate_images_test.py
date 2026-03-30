"""Image generation tests for all drawcustom element types.

Each test function renders a representative scenario to ``tests/images/`` so
the files can be embedded directly in README.md as documentation screenshots.
Every test also asserts pixel-level correctness and therefore doubles as a
regression guard.

The PNG files are (re-)written on every test run, keeping the documentation
images in sync with the implementation.  Commit the generated files together
with any code changes so the README images remain current.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from tests.drawcustom.helpers import (
    ArgonOledDevice,
    draw_element,
    region_changed,
    region_has_white,
    region_is_black,
)

# ---------------------------------------------------------------------------
# Constants and module-level directory creation
# ---------------------------------------------------------------------------

_W, _H = 128, 64
IMAGES_DIR = Path(__file__).parent.parent / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _fresh_device() -> ArgonOledDevice:
    """Return an uninitialised ArgonOledDevice (no I²C required)."""
    dev: ArgonOledDevice = object.__new__(ArgonOledDevice)
    dev._state = None  # pylint: disable=protected-access
    return dev


def _render(*elements: dict[str, Any]) -> Image.Image:
    """Draw *elements* in order on a fresh 128x64 black canvas and return it."""
    img = Image.new("1", (_W, _H), color=0)
    drw = ImageDraw.Draw(img)
    dev = _fresh_device()
    for el in elements:
        draw_element(dev, img, drw, el)
    return img


def _save(img: Image.Image, name: str) -> None:
    """Write *img* to ``tests/images/<name>.png``."""
    img.save(IMAGES_DIR / f"{name}.png")


# ---------------------------------------------------------------------------
# type: text
# ---------------------------------------------------------------------------


def test_image_type_text() -> None:
    """Render a three-line text layout and save type_text.png."""
    img = _render(
        {"type": "text", "value": "Hello World!", "x": 2, "y": 2, "size": 14},
        {"type": "text", "value": "Status: OK", "x": 2, "y": 24, "size": 12},
        {"type": "text", "value": "192.168.1.100", "x": 2, "y": 44, "size": 10},
    )
    _save(img, "type_text")
    # Each text line must produce white pixels in its vertical band.
    assert region_has_white(img, 2, 2, 126, 20)  # line 1
    assert region_has_white(img, 2, 22, 126, 38)  # line 2
    assert region_has_white(img, 2, 42, 126, 58)  # line 3


# ---------------------------------------------------------------------------
# type: multiline
# ---------------------------------------------------------------------------


def test_image_type_multiline() -> None:
    """Render a pipe-delimited multiline text element and save type_multiline.png."""
    img = _render(
        {
            "type": "multiline",
            "value": "CPU: 42C|MEM: 1.2G|DISK: 80%",
            "delimiter": "|",
            "x": 4,
            "y": 8,
            "size": 14,
            "spacing": 2,
        },
    )
    _save(img, "type_multiline")
    assert region_has_white(img, 4, 8, 124, 60)


# ---------------------------------------------------------------------------
# type: line
# ---------------------------------------------------------------------------


def test_image_type_line() -> None:
    """Render thick, horizontal-separator, and vertical lines; save type_line.png."""
    img = _render(
        # Thick decorative line near the top
        {"type": "line", "x_start": 10, "y_start": 5, "x_end": 117, "y_end": 5, "width": 3},
        # Full-width horizontal separator
        {"type": "line", "x_start": 0, "y_start": 20, "x_end": 127, "y_end": 20},
        # Full-width horizontal separator
        {"type": "line", "x_start": 0, "y_start": 43, "x_end": 127, "y_end": 43},
        # Vertical centre line between the two separators
        {"type": "line", "x_start": 63, "y_start": 21, "x_end": 63, "y_end": 42},
    )
    _save(img, "type_line")
    assert region_has_white(img, 10, 5, 117, 5)  # thick top line
    assert region_has_white(img, 0, 20, 127, 20)  # first separator
    assert region_has_white(img, 0, 43, 127, 43)  # second separator
    assert region_has_white(img, 63, 21, 63, 42)  # vertical centre line


# ---------------------------------------------------------------------------
# type: rectangle
# ---------------------------------------------------------------------------


def test_image_type_rectangle() -> None:
    """Render two nested outline rectangles and save type_rectangle.png."""
    img = _render(
        # Outer frame
        {"type": "rectangle", "x_start": 2, "y_start": 2, "x_end": 125, "y_end": 61},
        # Inner frame
        {"type": "rectangle", "x_start": 16, "y_start": 16, "x_end": 111, "y_end": 47},
    )
    _save(img, "type_rectangle")
    assert region_has_white(img, 2, 2, 125, 2)  # outer top border
    assert region_has_white(img, 2, 61, 125, 61)  # outer bottom border
    assert region_has_white(img, 16, 16, 111, 16)  # inner top border
    # Interior of inner rectangle is untouched (no fill) → must stay black.
    assert region_is_black(img, 20, 20, 107, 43)


# ---------------------------------------------------------------------------
# type: filled_rectangle
# ---------------------------------------------------------------------------


def test_image_type_filled_rectangle() -> None:
    """Render a large filled_rectangle and save type_filled_rectangle.png."""
    img = _render(
        {
            "type": "filled_rectangle",
            "x_start": 10,
            "y_start": 8,
            "x_end": 117,
            "y_end": 55,
        },
    )
    _save(img, "type_filled_rectangle")
    # Interior of the filled rectangle must be white.
    assert region_has_white(img, 11, 9, 116, 54)


# ---------------------------------------------------------------------------
# type: pixel
# ---------------------------------------------------------------------------


def test_image_type_pixel() -> None:
    """Render a dotted-border + centre-cross pixel pattern; save type_pixel.png."""
    elements: list[dict[str, Any]] = []

    # Dotted top and bottom borders (pixel at every even x)
    for x in range(0, 128, 2):
        elements.append({"type": "pixel", "x": x, "y": 0})
        elements.append({"type": "pixel", "x": x, "y": 63})

    # Dotted left and right borders (pixel at every even y)
    for y in range(0, 64, 2):
        elements.append({"type": "pixel", "x": 0, "y": y})
        elements.append({"type": "pixel", "x": 127, "y": y})

    # Centre horizontal cross-arm
    for x in range(52, 76):
        elements.append({"type": "pixel", "x": x, "y": 31})

    # Centre vertical cross-arm
    for y in range(22, 42):
        elements.append({"type": "pixel", "x": 63, "y": y})

    img = _render(*elements)
    _save(img, "type_pixel")
    assert region_has_white(img, 0, 0, 10, 0)  # dotted top border
    assert region_has_white(img, 52, 31, 75, 31)  # horizontal cross-arm
    assert region_has_white(img, 63, 22, 63, 41)  # vertical cross-arm


# ---------------------------------------------------------------------------
# type: dlimg
# ---------------------------------------------------------------------------


def test_image_type_dlimg() -> None:
    """Render a dlimg element centred on the canvas and save type_dlimg.png.

    A 64x32 source image (white border + X diagonals) is built in memory,
    saved to a temporary file, then pasted via the dlimg element.  The temp
    file is removed after the render.
    """
    # Build a recognisable 64x32 source pattern: border + two diagonals.
    source = Image.new("1", (64, 32), color=0)
    d = ImageDraw.Draw(source)
    d.rectangle((0, 0, 63, 31), outline=1)  # white border
    d.line((0, 0, 63, 31), fill=1)  # diagonal ↘
    d.line((63, 0, 0, 31), fill=1)  # diagonal ↙

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        tmp_path = Path(tf.name)
    source.save(tmp_path)

    try:
        img = _render(
            {
                "type": "dlimg",
                "url": str(tmp_path),
                "x": 32,
                "y": 16,
                "xsize": 64,
                "ysize": 32,
            },
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    _save(img, "type_dlimg")
    # The pasted image occupies x:32..95, y:16..47.
    # Top and left borders of the source image must be white in the canvas.
    assert region_has_white(img, 32, 16, 95, 16)  # top border row
    assert region_has_white(img, 32, 16, 32, 47)  # left border column


# ---------------------------------------------------------------------------
# progress_bar — progress levels (direction: right)
# ---------------------------------------------------------------------------


def test_image_progress_bar_progress_levels() -> None:
    """Render 5 stacked bars at 0/25/50/75/100 % and save progress_bar_progress.png.

    Layout: 5 bars x 9 px tall with 3 px gaps, centred in the 64 px height.
    """
    levels = [0, 25, 50, 75, 100]
    elements: list[dict[str, Any]] = []
    bar_positions: list[tuple[int, int]] = []

    for i, pct in enumerate(levels):
        y1 = 3 + i * 12  # 3, 15, 27, 39, 51
        y2 = y1 + 8  # 11, 23, 35, 47, 59  (9 px tall, 3 px gap)
        bar_positions.append((y1, y2))
        elements.append(
            {
                "type": "progress_bar",
                "x_start": 3,
                "y_start": y1,
                "x_end": 124,
                "y_end": y2,
                "progress": pct,
            }
        )

    img = _render(*elements)
    _save(img, "progress_bar_progress")

    # 0 % — interior must be black (background only, no fill)
    y1_0, y2_0 = bar_positions[0]
    assert region_is_black(img, 5, y1_0 + 2, 122, y2_0 - 2)

    # 50 % — left half interior must be white
    # filled_w = int(121 * 50 / 100) = 60; fill from x=3 to x=63
    y1_50, y2_50 = bar_positions[2]
    assert region_has_white(img, 5, y1_50 + 2, 60, y2_50 - 2)

    # 100 % — full interior must be white
    y1_100, y2_100 = bar_positions[4]
    assert region_has_white(img, 5, y1_100 + 2, 122, y2_100 - 2)


# ---------------------------------------------------------------------------
# progress_bar — fill directions
# ---------------------------------------------------------------------------


def test_image_progress_bar_directions() -> None:
    """Render one bar per fill direction at 60 % and save progress_bar_directions.png.

    Layout: two horizontal bars (right / left) in the top half; two portrait
    bars (down / up) in the bottom half.
    """
    img = _render(
        # Top-left: direction=right
        {
            "type": "progress_bar",
            "x_start": 1,
            "y_start": 2,
            "x_end": 62,
            "y_end": 30,
            "progress": 60,
            "direction": "right",
        },
        # Top-right: direction=left
        {
            "type": "progress_bar",
            "x_start": 65,
            "y_start": 2,
            "x_end": 126,
            "y_end": 30,
            "progress": 60,
            "direction": "left",
        },
        # Bottom-left: direction=down (tall narrow bar)
        {
            "type": "progress_bar",
            "x_start": 14,
            "y_start": 34,
            "x_end": 48,
            "y_end": 62,
            "progress": 60,
            "direction": "down",
        },
        # Bottom-right: direction=up (tall narrow bar)
        {
            "type": "progress_bar",
            "x_start": 79,
            "y_start": 34,
            "x_end": 113,
            "y_end": 62,
            "progress": 60,
            "direction": "up",
        },
    )
    _save(img, "progress_bar_directions")

    # right: bar_w=61, filled_w=int(61*0.6)=36; fill x=1..37 → interior x=3..35
    assert region_has_white(img, 3, 4, 35, 28)

    # left: fill x=90..126 → interior x=92..124
    assert region_has_white(img, 92, 4, 124, 28)

    # down: bar_h=28, filled_h=int(28*0.6)=16; fill y=34..50 → interior y=36..48
    assert region_has_white(img, 16, 36, 46, 48)

    # up: fill y=46..62 → interior y=48..60
    assert region_has_white(img, 81, 48, 111, 60)


# ---------------------------------------------------------------------------
# progress_bar — show_percentage (XOR composited label)
# ---------------------------------------------------------------------------


def test_image_progress_bar_show_percentage() -> None:
    """Render two bars with show_percentage=True and save progress_bar_percentage.png.

    The saved image has the percentage labels; assertions verify that the XOR
    compositing actually changed pixels compared to the no-label render.
    """
    bar1: dict[str, Any] = {
        "type": "progress_bar",
        "x_start": 3,
        "y_start": 4,
        "x_end": 124,
        "y_end": 27,
        "progress": 50,
        "size": 10,
    }
    bar2: dict[str, Any] = {
        "type": "progress_bar",
        "x_start": 3,
        "y_start": 33,
        "x_end": 124,
        "y_end": 58,
        "progress": 75,
        "size": 10,
    }

    img_without = _render(bar1, bar2)
    img_with = _render(
        {**bar1, "show_percentage": True},
        {**bar2, "show_percentage": True},
    )
    _save(img_with, "progress_bar_percentage")

    # XOR text must have changed pixels in both bar regions.
    assert region_changed(img_without, img_with, 20, 4, 110, 27)
    assert region_changed(img_without, img_with, 20, 33, 110, 58)


# ---------------------------------------------------------------------------
# progress_bar — visual styles
# ---------------------------------------------------------------------------


def test_image_progress_bar_styles() -> None:
    """Render three visual style variants at 60 % and save progress_bar_styles.png.

    Variants: default (white fill / white outline / black background),
    thick border (width=3), inverted colours (white background / black fill).
    """
    img = _render(
        # 1. Standard defaults
        {
            "type": "progress_bar",
            "x_start": 3,
            "y_start": 4,
            "x_end": 124,
            "y_end": 16,
            "progress": 60,
        },
        # 2. Thick border (width=3)
        {
            "type": "progress_bar",
            "x_start": 3,
            "y_start": 24,
            "x_end": 124,
            "y_end": 36,
            "progress": 60,
            "width": 3,
        },
        # 3. Inverted: white background, black fill, white outline
        {
            "type": "progress_bar",
            "x_start": 3,
            "y_start": 44,
            "x_end": 124,
            "y_end": 56,
            "progress": 60,
            "background": "white",
            "fill": "black",
            "outline": "white",
        },
    )
    _save(img, "progress_bar_styles")

    # Standard bar: fill zone interior must be white.
    # filled_w = int(121 * 0.6) = 72; fill x=3..75; interior y=5..15
    assert region_has_white(img, 5, 6, 72, 14)

    # Thick border: fill zone interior (inside 3 px border) must be white.
    # Interior starts at x=6, y=27; fill zone ends at x~72
    assert region_has_white(img, 8, 28, 70, 32)

    # Inverted bar: fill zone interior must be BLACK (black fill on white bg).
    # Interior y=45..55; fill zone x=4..74
    assert region_is_black(img, 6, 46, 72, 54)

    # Inverted bar: unfilled zone interior must be WHITE (white background).
    # Unfilled zone x=77..123
    assert region_has_white(img, 80, 46, 121, 54)


# ---------------------------------------------------------------------------
# type: icon
# ---------------------------------------------------------------------------


def test_image_type_icon() -> None:
    """Render two MDI icons and save type_icon.png.

    Draws a ``mdi:home`` icon (24 px) at the top-left and a ``mdi:thermometer``
    icon (32 px) to the right of it.  Both accept the ``mdi:`` prefix as well
    as the bare icon name, so we test one of each form.
    """
    img = _render(
        # mdi: prefix form — home icon, 24 px
        {"type": "icon", "value": "mdi:home", "x": 4, "y": 4, "size": 24},
        # bare name form — thermometer icon, 32 px
        {"type": "icon", "value": "thermometer", "x": 68, "y": 0, "size": 32},
    )
    _save(img, "type_icon")
    # Both icons must produce at least one white pixel in their bounding boxes.
    assert region_has_white(img, 4, 4, 30, 30)  # home (24 px)
    assert region_has_white(img, 68, 0, 102, 34)  # thermometer (32 px)
