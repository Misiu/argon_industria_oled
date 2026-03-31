"""Unit tests for _draw_element color support in ArgonOledDevice.

Tests verify that each drawing element type respects the optional ``color``
attribute (``"white"`` = pixel-on = 1, ``"black"`` = pixel-off = 0) and that
the default color is white when ``color`` is omitted.

These tests run entirely in-memory using Pillow — no I²C hardware is required.
"""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Provide a minimal smbus2 stub so device.py can be imported without hardware
# ---------------------------------------------------------------------------
_smbus2_stub = types.ModuleType("smbus2")
_smbus2_stub.SMBus = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("smbus2", _smbus2_stub)

# ---------------------------------------------------------------------------
# Import device.py and its dependencies directly, bypassing __init__.py
# so that homeassistant is not required at import time.
# ---------------------------------------------------------------------------
_BASE = Path(__file__).parent.parent / "custom_components" / "argon_industria_oled"


def _load_module(name: str, path: Path) -> types.ModuleType:
    """Load a module from *path* and register it under *name* in sys.modules."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


# Load const first (no external dependencies)
_const = _load_module(
    "custom_components.argon_industria_oled.const",
    _BASE / "const.py",
)

# Load device (depends on const, smbus2, and PIL — all available)
_device_mod = _load_module(
    "custom_components.argon_industria_oled.device",
    _BASE / "device.py",
)

ArgonOledDevice = _device_mod.ArgonOledDevice
DeviceError = _device_mod.DeviceError

# pylint: disable=wrong-import-position
from PIL import Image, ImageDraw  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64


def _make_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """Return a blank (all-black) 128x64 monochrome image and its draw handle."""
    image = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=0)
    return image, ImageDraw.Draw(image)


def _device() -> ArgonOledDevice:
    """Return an ArgonOledDevice instance without initializing I²C."""
    dev: ArgonOledDevice = object.__new__(ArgonOledDevice)
    dev._state = None  # pylint: disable=protected-access
    return dev


def _any_pixel_set(image: Image.Image, x1: int, y1: int, x2: int, y2: int) -> bool:
    """Return True if at least one pixel in the bounding box is white (1)."""
    region = image.crop((x1, y1, x2 + 1, y2 + 1))
    return any(region.tobytes())


def _all_pixels_clear(image: Image.Image, x1: int, y1: int, x2: int, y2: int) -> bool:
    """Return True if every pixel in the bounding box is black (0)."""
    region = image.crop((x1, y1, x2 + 1, y2 + 1))
    return not any(region.tobytes())


# ---------------------------------------------------------------------------
# _color_value helper
# ---------------------------------------------------------------------------


class TestColorValue(unittest.TestCase):
    """Test the _color_value static helper."""

    def setUp(self) -> None:
        self.dev = _device()

    def test_default_is_white(self) -> None:
        """Omitting ``color`` yields 1 (white)."""
        self.assertEqual(self.dev._color_value({}), 1)  # pylint: disable=protected-access

    def test_explicit_white(self) -> None:
        self.assertEqual(self.dev._color_value({"color": "white"}), 1)  # pylint: disable=protected-access

    def test_explicit_black(self) -> None:
        self.assertEqual(self.dev._color_value({"color": "black"}), 0)  # pylint: disable=protected-access

    def test_case_insensitive(self) -> None:
        self.assertEqual(self.dev._color_value({"color": "BLACK"}), 0)  # pylint: disable=protected-access
        self.assertEqual(self.dev._color_value({"color": "White"}), 1)  # pylint: disable=protected-access


# ---------------------------------------------------------------------------
# ELEMENT_PIXEL
# ---------------------------------------------------------------------------


class TestPixelElement(unittest.TestCase):
    """Test the ``pixel`` element type with both color values."""

    def setUp(self) -> None:
        self.dev = _device()

    def _draw(self, element: dict[str, Any]) -> Image.Image:
        image, draw = _make_canvas()
        self.dev._draw_element(draw, image, element)  # pylint: disable=protected-access
        return image

    def test_pixel_white_default(self) -> None:
        """Pixel without explicit color is drawn white."""
        image = self._draw({"type": "pixel", "x": 10, "y": 10})
        self.assertEqual(image.getpixel((10, 10)), 1)

    def test_pixel_white_explicit(self) -> None:
        image = self._draw({"type": "pixel", "x": 10, "y": 10, "color": "white"})
        self.assertEqual(image.getpixel((10, 10)), 1)

    def test_pixel_black(self) -> None:
        """Pixel with color=black on a black canvas stays 0."""
        image = self._draw({"type": "pixel", "x": 10, "y": 10, "color": "black"})
        self.assertEqual(image.getpixel((10, 10)), 0)

    def test_pixel_black_on_white_canvas(self) -> None:
        """Drawing a black pixel on a white canvas clears the pixel."""
        image = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=1)
        draw = ImageDraw.Draw(image)
        self.dev._draw_element(  # pylint: disable=protected-access
            draw, image, {"type": "pixel", "x": 5, "y": 5, "color": "black"}
        )
        self.assertEqual(image.getpixel((5, 5)), 0)


# ---------------------------------------------------------------------------
# ELEMENT_LINE
# ---------------------------------------------------------------------------


class TestLineElement(unittest.TestCase):
    """Test the ``line`` element type."""

    def setUp(self) -> None:
        self.dev = _device()

    def _draw(self, element: dict[str, Any]) -> Image.Image:
        image, draw = _make_canvas()
        self.dev._draw_element(draw, image, element)  # pylint: disable=protected-access
        return image

    def test_line_white_default(self) -> None:
        image = self._draw({"type": "line", "x_start": 0, "y_start": 32, "x_end": 20, "y_end": 32})
        self.assertTrue(_any_pixel_set(image, 0, 32, 20, 32))

    def test_line_white_explicit(self) -> None:
        image = self._draw(
            {
                "type": "line",
                "x_start": 0,
                "y_start": 32,
                "x_end": 20,
                "y_end": 32,
                "color": "white",
            }
        )
        self.assertTrue(_any_pixel_set(image, 0, 32, 20, 32))

    def test_line_black_does_not_set_pixels(self) -> None:
        """A black line on a black canvas leaves all pixels at 0."""
        image = self._draw(
            {
                "type": "line",
                "x_start": 0,
                "y_start": 32,
                "x_end": 20,
                "y_end": 32,
                "color": "black",
            }
        )
        self.assertTrue(_all_pixels_clear(image, 0, 32, 20, 32))

    def test_line_black_erases_on_white_canvas(self) -> None:
        """A black line on a white canvas clears pixels along the line."""
        image = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=1)
        draw = ImageDraw.Draw(image)
        self.dev._draw_element(  # pylint: disable=protected-access
            draw,
            image,
            {
                "type": "line",
                "x_start": 0,
                "y_start": 10,
                "x_end": 50,
                "y_end": 10,
                "color": "black",
            },
        )
        self.assertTrue(_all_pixels_clear(image, 0, 10, 50, 10))


# ---------------------------------------------------------------------------
# ELEMENT_RECTANGLE (outline only)
# ---------------------------------------------------------------------------


class TestRectangleElement(unittest.TestCase):
    """Test the ``rectangle`` element type."""

    def setUp(self) -> None:
        self.dev = _device()

    def _draw(self, element: dict[str, Any]) -> Image.Image:
        image, draw = _make_canvas()
        self.dev._draw_element(draw, image, element)  # pylint: disable=protected-access
        return image

    def test_rectangle_outline_white_default(self) -> None:
        """Rectangle outline is white by default."""
        image = self._draw(
            {"type": "rectangle", "x_start": 5, "y_start": 5, "x_end": 50, "y_end": 40}
        )
        self.assertTrue(_any_pixel_set(image, 5, 5, 50, 5))

    def test_rectangle_black_outline(self) -> None:
        """Rectangle with color=black does not light up pixels on a black canvas."""
        image = self._draw(
            {
                "type": "rectangle",
                "x_start": 5,
                "y_start": 5,
                "x_end": 50,
                "y_end": 40,
                "color": "black",
            }
        )
        self.assertTrue(_all_pixels_clear(image, 5, 5, 50, 40))

    def test_rectangle_with_fill(self) -> None:
        """fill=True fills the interior with the element color."""
        image = self._draw(
            {
                "type": "rectangle",
                "x_start": 5,
                "y_start": 5,
                "x_end": 50,
                "y_end": 40,
                "fill": True,
                "color": "white",
            }
        )
        self.assertTrue(_any_pixel_set(image, 10, 10, 45, 35))

    def test_rectangle_no_fill_leaves_interior_unchanged(self) -> None:
        """fill=False (default) does not fill the interior."""
        image = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=1)
        draw = ImageDraw.Draw(image)
        self.dev._draw_element(  # pylint: disable=protected-access
            draw,
            image,
            {"type": "rectangle", "x_start": 10, "y_start": 10, "x_end": 50, "y_end": 40},
        )
        # Interior pixels should still be white (untouched)
        self.assertTrue(_any_pixel_set(image, 15, 15, 45, 35))


# ---------------------------------------------------------------------------
# ELEMENT_TEXT
# ---------------------------------------------------------------------------


class TestTextElement(unittest.TestCase):
    """Test the ``text`` element type."""

    def setUp(self) -> None:
        self.dev = _device()

    def _draw(self, element: dict[str, Any]) -> Image.Image:
        image, draw = _make_canvas()
        self.dev._draw_element(draw, image, element)  # pylint: disable=protected-access
        return image

    def test_text_white_default_sets_pixels(self) -> None:
        """Text without explicit color sets at least one white pixel."""
        image = self._draw({"type": "text", "x": 0, "y": 0, "value": "A", "size": 10})
        self.assertTrue(_any_pixel_set(image, 0, 0, 20, 15))

    def test_text_black_on_white_canvas_clears_pixels(self) -> None:
        """Black text on a white canvas changes at least some pixels."""
        from PIL import ImageChops

        before = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=1)
        after = before.copy()
        draw = ImageDraw.Draw(after)
        self.dev._draw_element(  # pylint: disable=protected-access
            draw,
            after,
            {"type": "text", "x": 0, "y": 0, "value": "A", "size": 10, "color": "black"},
        )
        diff = ImageChops.difference(before, after)
        self.assertIsNotNone(diff.getbbox())


# ---------------------------------------------------------------------------
# ELEMENT_MULTILINE
# ---------------------------------------------------------------------------


class TestMultilineElement(unittest.TestCase):
    """Test the ``multiline`` element type."""

    def setUp(self) -> None:
        self.dev = _device()

    def _draw(self, element: dict[str, Any]) -> Image.Image:
        image, draw = _make_canvas()
        self.dev._draw_element(draw, image, element)  # pylint: disable=protected-access
        return image

    def test_multiline_white_default_sets_pixels(self) -> None:
        image = self._draw({"type": "multiline", "x": 0, "y": 0, "value": "Hi|there", "size": 8})
        self.assertTrue(_any_pixel_set(image, 0, 0, 40, 30))

    def test_multiline_black_clears_on_white_canvas(self) -> None:
        """Black multiline text on a white canvas changes at least some pixels."""
        from PIL import ImageChops

        before = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=1)
        after = before.copy()
        draw = ImageDraw.Draw(after)
        self.dev._draw_element(  # pylint: disable=protected-access
            draw,
            after,
            {"type": "multiline", "x": 0, "y": 0, "value": "Hi|there", "size": 8, "color": "black"},
        )
        diff = ImageChops.difference(before, after)
        self.assertIsNotNone(diff.getbbox())


# ---------------------------------------------------------------------------
# Unsupported element type
# ---------------------------------------------------------------------------


class TestUnsupportedElement(unittest.TestCase):
    def setUp(self) -> None:
        self.dev = _device()

    def test_raises_device_error(self) -> None:
        image, draw = _make_canvas()
        with self.assertRaises(DeviceError):
            self.dev._draw_element(draw, image, {"type": "unknown_type"})  # pylint: disable=protected-access


if __name__ == "__main__":
    unittest.main()
