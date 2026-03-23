"""Hardware device layer for the Argon Industria OLED module."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

try:  # pragma: no cover - runtime import guard
    from luma.core.interface.serial import i2c
    from luma.oled.device import ssd1306
except ImportError as err:  # pragma: no cover - runtime import guard
    raise RuntimeError("luma.oled must be installed to use this integration") from err

try:  # pragma: no cover - runtime import guard
    from PIL import Image, ImageDraw, ImageFont
except ImportError as err:  # pragma: no cover - runtime import guard
    raise RuntimeError("Pillow must be installed to use this integration") from err

from .const import (
    DEFAULT_I2C_ADDRESS,
    DEFAULT_I2C_BUS,
    DISPLAY_HEIGHT,
    DISPLAY_WIDTH,
    ELEMENT_FILLED_RECTANGLE,
    ELEMENT_IMAGE,
    ELEMENT_LINE,
    ELEMENT_MULTILINE_TEXT,
    ELEMENT_PIXEL,
    ELEMENT_RECTANGLE,
    ELEMENT_TEXT,
    RETRY_ATTEMPTS,
    RETRY_DELAY_SECONDS,
    SPLASH,
    SUPPORTED_ELEMENT_TYPES,
)

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class DeviceError(Exception):
    """Base class for OLED device errors."""


class DeviceNotFoundError(DeviceError):
    """Raised when no OLED device is reachable on I2C."""


class DeviceInitializeError(DeviceError):
    """Raised when OLED initialization fails."""


@dataclass(slots=True)
class _DeviceState:
    """Runtime handles for the OLED device."""

    oled: Any
    framebuffer: Image.Image


class ArgonOledDevice:
    """Manage SSD1306 initialization and canvas rendering for the OLED panel."""

    def __init__(self, bus: int = DEFAULT_I2C_BUS, address: int = DEFAULT_I2C_ADDRESS) -> None:
        self._bus = bus
        self._address = address
        self._state: _DeviceState | None = None

    @property
    def bus(self) -> int:
        """Return the I2C bus number."""
        return self._bus

    @property
    def address(self) -> int:
        """Return the I2C address."""
        return self._address

    def probe(self) -> bool:
        """Return True when the display responds to initialization and clear operations."""

        def operation() -> bool:
            self._init_device()
            self.clear()
            return True

        try:
            return self._retry(operation, context="probe")
        except DeviceError:
            return False

    def initialize(self) -> None:
        """Initialize the OLED display and ensure it can be written."""

        def operation() -> None:
            self._init_device()
            self.clear()

        self._retry(operation, context="initialize")

    def clear(self) -> None:
        """Clear the display."""
        state = self._require_state()
        state.oled.clear()
        state.framebuffer = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=0)

    def show_startup(self) -> None:
        """Render startup splash image from constant bitmap bytes."""

        def operation() -> None:
            state = self._require_state()
            splash_image = self._image_from_splash_bytes()
            state.oled.display(splash_image)
            state.framebuffer = splash_image

        self._retry(operation, context="show_startup")

    def _image_from_splash_bytes(self) -> Image.Image:
        """Convert SSD1306 page-formatted splash bytes to a Pillow image."""
        expected_size = (DISPLAY_WIDTH * DISPLAY_HEIGHT) // 8
        raw_splash = SPLASH
        if len(raw_splash) < expected_size:
            _LOGGER.warning(
                "SPLASH shorter than expected (%s < %s), padding with zeros",
                len(raw_splash),
                expected_size,
            )
            raw_splash = raw_splash + bytes(expected_size - len(raw_splash))
        elif len(raw_splash) > expected_size:
            _LOGGER.warning(
                "SPLASH longer than expected (%s > %s), truncating",
                len(raw_splash),
                expected_size,
            )
            raw_splash = raw_splash[:expected_size]

        image = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=0)
        pixels = image.load()
        page_height = 8
        page_count = DISPLAY_HEIGHT // page_height

        for page in range(page_count):
            page_offset = page * DISPLAY_WIDTH
            for x in range(DISPLAY_WIDTH):
                byte_value = raw_splash[page_offset + x]
                for bit in range(page_height):
                    y = page * page_height + bit
                    if (byte_value >> bit) & 0x01:
                        pixels[x, y] = 1

        return image

    def draw(self, elements: list[dict[str, Any]], clear: bool = True) -> None:
        """Render drawing elements to a framebuffer and flush once."""

        def operation() -> None:
            state = self._require_state()
            image = (
                Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=0)
                if clear
                else state.framebuffer.copy()
            )
            drawer = ImageDraw.Draw(image)

            for element in elements:
                self._draw_element(drawer, image, element)

            state.oled.display(image)
            state.framebuffer = image

        self._retry(operation, context="draw")

    def _draw_element(self, drawer: ImageDraw.ImageDraw, canvas: Image.Image, element: dict[str, Any]) -> None:
        """Draw one element onto the in-memory framebuffer."""
        element_type = str(element.get("type", "")).lower()
        if element_type not in SUPPORTED_ELEMENT_TYPES:
            raise DeviceError(f"Unsupported element type: {element_type}")

        if element_type == ELEMENT_TEXT:
            font = self._load_font(element.get("font_size"))
            x = self._clamp_x(element.get("x", 0))
            y = self._clamp_y(element.get("y", 0))
            value = str(element.get("value", ""))
            drawer.text((x, y), value, font=font, fill=1)
            return

        if element_type == ELEMENT_MULTILINE_TEXT:
            font = self._load_font(element.get("font_size"))
            x = self._clamp_x(element.get("x", 0))
            y = self._clamp_y(element.get("y", 0))
            value = str(element.get("value", ""))
            spacing = max(0, int(element.get("spacing", 2)))
            drawer.multiline_text((x, y), value, font=font, fill=1, spacing=spacing)
            return

        if element_type == ELEMENT_LINE:
            drawer.line(
                (
                    self._clamp_x(element.get("x1", 0)),
                    self._clamp_y(element.get("y1", 0)),
                    self._clamp_x(element.get("x2", 0)),
                    self._clamp_y(element.get("y2", 0)),
                ),
                fill=1,
            )
            return

        if element_type in (ELEMENT_RECTANGLE, ELEMENT_FILLED_RECTANGLE):
            x = self._clamp_x(element.get("x", 0))
            y = self._clamp_y(element.get("y", 0))
            width = max(1, int(element.get("width", 1)))
            height = max(1, int(element.get("height", 1)))
            x2 = self._clamp_x(x + width - 1)
            y2 = self._clamp_y(y + height - 1)
            if element_type == ELEMENT_RECTANGLE:
                drawer.rectangle((x, y, x2, y2), outline=1, fill=1 if bool(element.get("fill")) else 0)
            else:
                drawer.rectangle((x, y, x2, y2), outline=1 if bool(element.get("outline", True)) else 0, fill=1)
            return

        if element_type == ELEMENT_PIXEL:
            x = self._clamp_x(element.get("x", 0))
            y = self._clamp_y(element.get("y", 0))
            drawer.point((x, y), fill=1)
            return

        if element_type == ELEMENT_IMAGE:
            self._draw_image(canvas, element)
            return

    def _draw_image(self, canvas: Image.Image, element: dict[str, Any]) -> None:
        """Render a source image onto the framebuffer with clipping."""
        source = element.get("path")
        if not source:
            raise DeviceError("Image element requires a 'path' field")

        image_path = Path(str(source))
        if not image_path.exists():
            raise DeviceError(f"Image file not found: {image_path}")

        with Image.open(image_path) as opened:
            image = opened.convert("1")
            width = int(element.get("width", image.width))
            height = int(element.get("height", image.height))
            if width > 0 and height > 0 and (width != image.width or height != image.height):
                image = image.resize((width, height))

            x = self._clamp_x(element.get("x", 0))
            y = self._clamp_y(element.get("y", 0))
            canvas.paste(image, (x, y))

    def _load_font(self, font_size: Any) -> ImageFont.ImageFont:
        """Load a readable default font with optional size hint."""
        size = max(6, int(font_size)) if font_size is not None else 12
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except OSError:
            return ImageFont.load_default()

    def _init_device(self) -> None:
        """Open and initialize the OLED device if needed."""
        if self._state is not None:
            return

        self._ensure_i2c_bus_path()

        try:
            serial = i2c(port=self._bus, address=self._address)
            oled = ssd1306(serial_interface=serial, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT)
            self._state = _DeviceState(
                oled=oled,
                framebuffer=Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=0),
            )
        except OSError as err:
            raise DeviceNotFoundError(
                f"I2C device not found on bus {self._bus} at address 0x{self._address:02x}: {err}"
            ) from err
        except Exception as err:  # noqa: BLE001
            raise DeviceInitializeError(f"Could not initialize SSD1306: {err}") from err

    def _require_state(self) -> _DeviceState:
        """Return initialized state or raise initialization error."""
        if self._state is None:
            raise DeviceInitializeError("OLED device is not initialized")
        return self._state

    def _ensure_i2c_bus_path(self) -> None:
        """Ensure expected Linux I2C device path exists."""
        bus_path = Path(f"/dev/i2c-{self._bus}")
        if not bus_path.exists():
            raise DeviceNotFoundError(f"I2C bus path is missing: {bus_path}")

    def close(self) -> None:
        """Close runtime resources."""
        self._state = None

    def _retry(self, func: Callable[[], T], context: str) -> T:
        """Run operation with bounded retries for transient hardware faults."""
        last_error: Exception | None = None

        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                return func()
            except DeviceError as err:
                last_error = err
            except Exception as err:  # noqa: BLE001
                last_error = DeviceError(str(err))

            _LOGGER.warning(
                "OLED %s attempt %s/%s failed: %s",
                context,
                attempt,
                RETRY_ATTEMPTS,
                last_error,
            )
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)

            self.close()

        assert last_error is not None
        raise last_error

    @staticmethod
    def _clamp_x(value: Any) -> int:
        """Clamp an x coordinate to display bounds."""
        return max(0, min(DISPLAY_WIDTH - 1, int(value)))

    @staticmethod
    def _clamp_y(value: Any) -> int:
        """Clamp a y coordinate to display bounds."""
        return max(0, min(DISPLAY_HEIGHT - 1, int(value)))

