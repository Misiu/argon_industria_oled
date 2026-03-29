"""Unit tests for the image entity and device framebuffer PNG export.

Tests run entirely in-memory using Pillow — no I²C hardware is required.
"""

from __future__ import annotations

import importlib.util
import io
import sys
import types
import unittest
from contextlib import suppress
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
# Import device.py directly, bypassing __init__.py
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


_const = _load_module(
    "custom_components.argon_industria_oled.const",
    _BASE / "const.py",
)
_device_mod = _load_module(
    "custom_components.argon_industria_oled.device",
    _BASE / "device.py",
)

ArgonOledDevice = _device_mod.ArgonOledDevice
_DeviceState = _device_mod._DeviceState  # pylint: disable=protected-access

from PIL import Image  # noqa: E402

DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64


def _device_without_state() -> Any:
    """Return an ArgonOledDevice instance with no initialized I²C state."""
    dev: ArgonOledDevice = object.__new__(ArgonOledDevice)
    dev._state = None  # pylint: disable=protected-access
    return dev


def _device_with_framebuffer(image: Image.Image) -> Any:
    """Return an ArgonOledDevice whose framebuffer is set to *image*."""
    dev: ArgonOledDevice = object.__new__(ArgonOledDevice)
    dev._state = _DeviceState(bus=MagicMock(), framebuffer=image)  # pylint: disable=protected-access
    return dev


# ---------------------------------------------------------------------------
# get_framebuffer_png_bytes — device not initialized
# ---------------------------------------------------------------------------


class TestGetFramebufferPngBytesNotInitialized(unittest.TestCase):
    """When the device is not initialized, png export returns None."""

    def test_returns_none_when_state_is_none(self) -> None:
        dev = _device_without_state()
        self.assertIsNone(dev.get_framebuffer_png_bytes())


# ---------------------------------------------------------------------------
# get_framebuffer_png_bytes — black framebuffer
# ---------------------------------------------------------------------------


class TestGetFramebufferPngBytesBlack(unittest.TestCase):
    """PNG export of a fully-black framebuffer."""

    def setUp(self) -> None:
        self.image = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=0)
        self.dev = _device_with_framebuffer(self.image)

    def test_returns_bytes(self) -> None:
        result = self.dev.get_framebuffer_png_bytes()
        self.assertIsInstance(result, bytes)

    def test_returns_non_empty_bytes(self) -> None:
        result = self.dev.get_framebuffer_png_bytes()
        self.assertGreater(len(result), 0)  # type: ignore[arg-type]

    def test_is_valid_png(self) -> None:
        """The returned bytes can be opened by Pillow as a PNG."""
        result = self.dev.get_framebuffer_png_bytes()
        loaded = Image.open(io.BytesIO(result))  # type: ignore[arg-type]
        self.assertEqual(loaded.format, "PNG")

    def test_output_is_2x_scaled(self) -> None:
        """The PNG image is 2x the original display dimensions."""
        result = self.dev.get_framebuffer_png_bytes()
        loaded = Image.open(io.BytesIO(result))  # type: ignore[arg-type]
        self.assertEqual(loaded.size, (DISPLAY_WIDTH * 2, DISPLAY_HEIGHT * 2))

    def test_all_pixels_black(self) -> None:
        """A fully-black framebuffer produces an all-black PNG."""
        result = self.dev.get_framebuffer_png_bytes()
        loaded = Image.open(io.BytesIO(result)).convert("L")  # type: ignore[arg-type]
        self.assertFalse(any(loaded.tobytes()))


# ---------------------------------------------------------------------------
# get_framebuffer_png_bytes — white framebuffer
# ---------------------------------------------------------------------------


class TestGetFramebufferPngBytesWhite(unittest.TestCase):
    """PNG export of a fully-white framebuffer."""

    def setUp(self) -> None:
        self.image = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=1)
        self.dev = _device_with_framebuffer(self.image)

    def test_all_pixels_white(self) -> None:
        """A fully-white framebuffer produces an all-white PNG."""
        result = self.dev.get_framebuffer_png_bytes()
        loaded = Image.open(io.BytesIO(result)).convert("L")  # type: ignore[arg-type]
        self.assertTrue(all(b == 255 for b in loaded.tobytes()))


# ---------------------------------------------------------------------------
# get_framebuffer_png_bytes — mixed content
# ---------------------------------------------------------------------------


class TestGetFramebufferPngBytesMixed(unittest.TestCase):
    """PNG export faithfully encodes mixed pixel content."""

    def test_white_pixel_in_black_canvas(self) -> None:
        """A single white pixel at (0, 0) is present in the exported PNG."""
        image = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=0)
        image.putpixel((0, 0), 1)
        dev = _device_with_framebuffer(image)

        result = dev.get_framebuffer_png_bytes()
        loaded = Image.open(io.BytesIO(result)).convert("L")  # type: ignore[arg-type]
        # The top-left 4x4 block should be white (pixel (0,0) scaled 4x)
        self.assertEqual(loaded.getpixel((0, 0)), 255)

    def test_black_pixel_in_white_canvas(self) -> None:
        """A single black pixel at (0, 0) is present in the exported PNG."""
        image = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=1)
        image.putpixel((0, 0), 0)
        dev = _device_with_framebuffer(image)

        result = dev.get_framebuffer_png_bytes()
        loaded = Image.open(io.BytesIO(result)).convert("L")  # type: ignore[arg-type]
        self.assertEqual(loaded.getpixel((0, 0)), 0)


# ---------------------------------------------------------------------------
# Display update subscription
# ---------------------------------------------------------------------------


class _MinimalCoord:
    """Minimal reproduction of the coordinator's display update subscription.

    Used to verify subscribe/unsubscribe behaviour without importing the full
    coordinator (which would require live HomeAssistant stubs).
    """

    def __init__(self) -> None:
        self._display_callbacks: list[Any] = []

    def subscribe_display_update(self, cb: Any) -> Any:
        """Mirror of ArgonIndustriaOledCoordinator.subscribe_display_update."""
        self._display_callbacks.append(cb)

        def unsubscribe() -> None:
            with suppress(ValueError):
                self._display_callbacks.remove(cb)

        return unsubscribe

    def _notify_display_updated(self) -> None:
        """Mirror of ArgonIndustriaOledCoordinator._notify_display_updated."""
        for cb in list(self._display_callbacks):
            cb()


class TestDisplayUpdateSubscription(unittest.TestCase):
    """Verify subscribe_display_update / _notify_display_updated logic."""

    def test_subscribe_and_notify(self) -> None:
        """Registered callback is invoked on _notify_display_updated."""
        coord = _MinimalCoord()
        called: list[int] = []

        def cb() -> None:
            called.append(1)

        coord.subscribe_display_update(cb)
        coord._notify_display_updated()  # pylint: disable=protected-access
        self.assertEqual(called, [1])

    def test_unsubscribe_stops_notifications(self) -> None:
        """Unsubscribe callable prevents further notifications."""
        coord = _MinimalCoord()
        called: list[int] = []

        def cb() -> None:
            called.append(1)

        unsubscribe = coord.subscribe_display_update(cb)
        coord._notify_display_updated()  # pylint: disable=protected-access
        self.assertEqual(called, [1])

        unsubscribe()
        coord._notify_display_updated()  # pylint: disable=protected-access
        # still just one call — cb was unsubscribed
        self.assertEqual(called, [1])

    def test_multiple_callbacks(self) -> None:
        """All registered callbacks are called."""
        coord = _MinimalCoord()
        results: list[str] = []

        coord.subscribe_display_update(lambda: results.append("a"))
        coord.subscribe_display_update(lambda: results.append("b"))
        coord._notify_display_updated()  # pylint: disable=protected-access
        self.assertIn("a", results)
        self.assertIn("b", results)


if __name__ == "__main__":
    unittest.main()
