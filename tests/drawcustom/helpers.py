"""Shared helpers for drawcustom element rendering tests.

Provides module-loading helpers, constants, canvas factories, and assertion
utilities used across all per-element test files.  All operations run
in-memory via Pillow — no I²C hardware or Home Assistant runtime is required.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from PIL import Image, ImageChops, ImageDraw

# ---------------------------------------------------------------------------
# Stub smbus2 so device.py can be imported on any host
# ---------------------------------------------------------------------------
_smbus2_stub = types.ModuleType("smbus2")
_smbus2_stub.SMBus = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("smbus2", _smbus2_stub)

# ---------------------------------------------------------------------------
# Load const.py and device.py directly, bypassing the package __init__.py
# so that homeassistant is not required at import time.
# ---------------------------------------------------------------------------
_BASE = Path(__file__).parent.parent.parent / "custom_components" / "argon_industria_oled"


def _load_module(name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


_load_module("custom_components.argon_industria_oled.const", _BASE / "const.py")
_device_mod = _load_module("custom_components.argon_industria_oled.device", _BASE / "device.py")

ArgonOledDevice = _device_mod.ArgonOledDevice
DeviceError = _device_mod.DeviceError

# ---------------------------------------------------------------------------
# Display constants
# ---------------------------------------------------------------------------

DISPLAY_WIDTH: int = 128
DISPLAY_HEIGHT: int = 64


# ---------------------------------------------------------------------------
# Canvas factories
# ---------------------------------------------------------------------------


def make_device() -> ArgonOledDevice:
    """Return an ArgonOledDevice without initializing I²C."""
    dev: ArgonOledDevice = object.__new__(ArgonOledDevice)
    dev._state = None  # pylint: disable=protected-access
    return dev


def make_canvas(color: int = 0) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """Return a 128x64 monochrome image filled with *color* (0=black, 1=white)."""
    image = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=color)
    return image, ImageDraw.Draw(image)


# ---------------------------------------------------------------------------
# Drawing helper
# ---------------------------------------------------------------------------


def draw_element(
    dev: ArgonOledDevice,
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    element: dict[str, Any],
) -> None:
    """Call ``_draw_element`` on *dev* with the given canvas and element."""
    dev._draw_element(draw, image, element)  # pylint: disable=protected-access


# ---------------------------------------------------------------------------
# Pixel-level assertion helpers (Pillow 12 compatible — no getdata())
# ---------------------------------------------------------------------------


def images_equal(img1: Image.Image, img2: Image.Image) -> bool:
    """Return True if the two images are pixel-identical."""
    return ImageChops.difference(img1, img2).getbbox() is None


def region_has_white(image: Image.Image, x1: int, y1: int, x2: int, y2: int) -> bool:
    """Return True if at least one pixel in the bounding box is white (1).

    Uses ``tobytes()`` to avoid the deprecated ``getdata()`` API
    (deprecated in Pillow 12, removed in Pillow 14).
    """
    return any(image.crop((x1, y1, x2 + 1, y2 + 1)).tobytes())


def region_is_black(image: Image.Image, x1: int, y1: int, x2: int, y2: int) -> bool:
    """Return True if every pixel in the bounding box is black (0)."""
    return not any(image.crop((x1, y1, x2 + 1, y2 + 1)).tobytes())


def region_changed(
    before: Image.Image, after: Image.Image, x1: int, y1: int, x2: int, y2: int
) -> bool:
    """Return True if any pixel in the bounding box differs between *before* and *after*."""
    diff = ImageChops.difference(
        before.crop((x1, y1, x2 + 1, y2 + 1)),
        after.crop((x1, y1, x2 + 1, y2 + 1)),
    )
    return diff.getbbox() is not None
