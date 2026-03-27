"""Hardware device layer for the Argon Industria OLED module."""

from __future__ import annotations

import io
import logging
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

try:  # pragma: no cover - runtime import guard
    from smbus2 import SMBus
except ImportError as err:  # pragma: no cover - runtime import guard
    raise RuntimeError("smbus2 must be installed to use this integration") from err

try:  # pragma: no cover - runtime import guard
    from PIL import Image, ImageDraw, ImageFont
except ImportError as err:  # pragma: no cover - runtime import guard
    raise RuntimeError("Pillow must be installed to use this integration") from err

from .const import (
    COLOR_BLACK,
    DEFAULT_I2C_ADDRESS,
    DEFAULT_I2C_BUS,
    DISPLAY_HEIGHT,
    DISPLAY_WIDTH,
    ELEMENT_DLIMG,
    ELEMENT_FILLED_RECTANGLE,
    ELEMENT_LINE,
    ELEMENT_MULTILINE,
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

_COMMAND_CONTROL_BYTE = 0x00
_DATA_CONTROL_BYTE = 0x6A
_COLUMN_OFFSET = 2
_PAGE_HEIGHT = 8
_PAGE_COUNT = DISPLAY_HEIGHT // _PAGE_HEIGHT
_WRITE_CHUNK = 16
_INIT_SEQUENCE: tuple[int, ...] = (
    0xAE,
    0xD5,
    0x80,
    0xA8,
    0x3F,
    0xD3,
    0x00,
    0x40,
    0xA1,
    0xC8,
    0xDA,
    0x12,
    0x81,
    0x7F,
    0xD9,
    0x22,
    0xDB,
    0x35,
    0xA4,
    0xA6,
    0x8D,
    0x14,
    0xAF,
)


class DeviceError(Exception):
    """Base class for OLED device errors."""


class DeviceNotFoundError(DeviceError):
    """Raised when no OLED device is reachable on I2C."""


class DeviceInitializeError(DeviceError):
    """Raised when OLED initialization fails."""


@dataclass(slots=True)
class _DeviceState:
    """Runtime handles for the OLED device."""

    bus: SMBus
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
        """Return True if the display responds to the SSD1306 initialization sequence.

        Sends the standard init commands over I²C to verify the device is present
        and reachable.  Does not write pixel data or alter the displayed content.
        """
        try:
            self._init_device()
            return True
        except DeviceError:
            return False

    def initialize(self) -> None:
        """Open the I²C bus and send the SSD1306 init sequence.

        Idempotent: safe to call multiple times; no-op when already initialized.
        Does not clear or modify the framebuffer.
        """
        self._retry(self._init_device, context="initialize")

    def clear(self) -> None:
        """Clear the display and reset the framebuffer to black."""

        def operation() -> None:
            state = self._require_state()
            blank = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=0)
            self._write_image(state.bus, blank)
            state.framebuffer = blank

        self._retry(operation, context="clear")

    def show_startup(self) -> None:
        """Render startup splash image from constant bitmap bytes."""

        def operation() -> None:
            state = self._require_state()
            splash_image = self._image_from_splash_bytes()
            self._write_image(state.bus, splash_image)
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
        if pixels is None:
            raise DeviceInitializeError("Could not get splash image pixel buffer")

        for page in range(_PAGE_COUNT):
            page_offset = page * DISPLAY_WIDTH
            for x in range(DISPLAY_WIDTH):
                byte_value = raw_splash[page_offset + x]
                for bit in range(_PAGE_HEIGHT):
                    y = page * _PAGE_HEIGHT + bit
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

            self._write_image(state.bus, image)
            state.framebuffer = image

        self._retry(operation, context="draw")

    def _draw_element(  # pylint: disable=too-many-locals
        self, drawer: ImageDraw.ImageDraw, canvas: Image.Image, element: dict[str, Any]
    ) -> None:
        """Draw one element onto the in-memory framebuffer."""
        element_type = str(element.get("type", "")).lower()
        if element_type not in SUPPORTED_ELEMENT_TYPES:
            raise DeviceError(f"Unsupported element type: {element_type}")

        color = self._color_value(element)

        if element_type == ELEMENT_TEXT:
            font = self._load_font(element.get("size"))
            x = self._clamp_x(element.get("x", 0))
            y = self._clamp_y(element.get("y", 0))
            value = str(element.get("value", ""))
            drawer.text((x, y), value, font=font, fill=color)
            return

        if element_type == ELEMENT_MULTILINE:
            font = self._load_font(element.get("size"))
            x = self._clamp_x(element.get("x", 0))
            y = self._clamp_y(element.get("y", 0))
            spacing = max(0, int(element.get("spacing", 2)))
            delimiter = str(element.get("delimiter", "|"))
            offset_y = int(element.get("offset_y", 0))
            lines = str(element.get("value", "")).split(delimiter)
            value = "\n".join(lines)
            drawer.multiline_text((x, y + offset_y), value, font=font, fill=color, spacing=spacing)
            return

        if element_type == ELEMENT_LINE:
            x1 = self._clamp_x(element.get("x_start", 0))
            y1 = self._clamp_y(element.get("y_start", 0))
            x2 = self._clamp_x(element.get("x_end", 0))
            y2 = self._clamp_y(element.get("y_end", y1))
            width = max(1, int(element.get("width", 1)))
            drawer.line((x1, y1, x2, y2), fill=color, width=width)
            return

        if element_type in (ELEMENT_RECTANGLE, ELEMENT_FILLED_RECTANGLE):
            x1 = self._clamp_x(element.get("x_start", 0))
            y1 = self._clamp_y(element.get("y_start", 0))
            x2 = self._clamp_x(element.get("x_end", x1))
            y2 = self._clamp_y(element.get("y_end", y1))

            if element_type == ELEMENT_RECTANGLE:
                fill: int | None = color if bool(element.get("fill", False)) else None
                drawer.rectangle((x1, y1, x2, y2), outline=color, fill=fill)
            else:
                outline: int | None = color if bool(element.get("outline", True)) else None
                drawer.rectangle((x1, y1, x2, y2), outline=outline, fill=color)
            return

        if element_type == ELEMENT_PIXEL:
            x = self._clamp_x(element.get("x", 0))
            y = self._clamp_y(element.get("y", 0))
            drawer.point((x, y), fill=color)
            return

        if element_type == ELEMENT_DLIMG:
            self._draw_image(canvas, element)
            return

    def _draw_image(self, canvas: Image.Image, element: dict[str, Any]) -> None:
        """Render a source image onto the framebuffer with clipping."""
        source = element.get("url")
        if not source:
            raise DeviceError("dlimg element requires 'url'")

        image_path = Path(str(source))
        if not image_path.exists():
            raise DeviceError(f"Image file not found: {image_path}")

        with Image.open(image_path) as opened:
            image = opened.convert("1")
            width = int(element.get("xsize", element.get("width", image.width)))
            height = int(element.get("ysize", element.get("height", image.height)))
            if width > 0 and height > 0 and (width != image.width or height != image.height):
                image = image.resize((width, height))

            x = self._clamp_x(element.get("x", 0))
            y = self._clamp_y(element.get("y", 0))
            canvas.paste(image, (x, y))

    def _load_font(self, font_size: Any) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Load a readable default font with optional size hint.

        Tries to load ``DejaVuSans.ttf`` from the system font path first.
        Falls back to Pillow's built-in font at the same size (the ``size``
        parameter for ``load_default`` was added in Pillow 10.1.0).
        """
        size = max(6, int(font_size)) if font_size is not None else 20
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except OSError:
            return ImageFont.load_default(size)

    def _init_device(self) -> None:
        """Open and initialize the OLED device if needed."""
        if self._state is not None:
            return

        self._ensure_i2c_bus_path()

        try:
            bus_handle = SMBus(self._bus)
            self._write_commands(bus_handle, _INIT_SEQUENCE)
            self._state = _DeviceState(
                bus=bus_handle,
                framebuffer=Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=0),
            )
        except FileNotFoundError as err:
            raise DeviceNotFoundError(f"I2C bus {self._bus} is not available: {err}") from err
        except OSError as err:
            raise DeviceNotFoundError(
                f"I2C device not found on bus {self._bus} at address 0x{self._address:02x}: {err}"
            ) from err
        except Exception as err:
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

    def _write_image(self, bus: SMBus, image: Image.Image) -> None:
        """Write image framebuffer to display pages."""
        pixels = image.load()
        if pixels is None:
            raise DeviceError("Could not get image pixel buffer")
        for page in range(_PAGE_COUNT):
            self._write_commands(
                bus,
                (
                    0xB0 + page,
                    (_COLUMN_OFFSET & 0x0F),
                    0x10 | ((_COLUMN_OFFSET >> 4) & 0x0F),
                ),
            )

            page_data: list[int] = []
            for column in range(DISPLAY_WIDTH):
                byte = 0
                for bit in range(_PAGE_HEIGHT):
                    y = page * _PAGE_HEIGHT + bit
                    if pixels[column, y]:
                        byte |= 1 << bit
                page_data.append(byte)

            self._write_data(bus, page_data)

    def _write_commands(self, bus: SMBus, commands: tuple[int, ...] | list[int]) -> None:
        """Send command bytes to OLED."""
        for command in commands:
            try:
                bus.write_byte_data(self._address, _COMMAND_CONTROL_BYTE, command & 0xFF)
            except OSError as err:
                raise DeviceError(f"Failed to write OLED command 0x{command:02X}: {err}") from err

    def _write_data(self, bus: SMBus, data: list[int]) -> None:
        """Send image data in bounded chunks."""
        for index in range(0, len(data), _WRITE_CHUNK):
            chunk = list(data[index : index + _WRITE_CHUNK])
            try:
                bus.write_i2c_block_data(self._address, _DATA_CONTROL_BYTE, chunk)
            except OSError as err:
                raise DeviceError(f"Failed to write OLED data: {err}") from err

    def get_framebuffer_png_bytes(self) -> bytes | None:
        """Return the current framebuffer as a scaled-up PNG, or None if not initialized.

        The 1-bit monochrome framebuffer is converted to grayscale and scaled 4x
        with nearest-neighbour resampling so the preview remains crisp and legible
        in the Home Assistant UI.
        """
        if self._state is None:
            return None
        image = self._state.framebuffer.convert("L").resize(
            (DISPLAY_WIDTH * 4, DISPLAY_HEIGHT * 4),
            resample=Image.Resampling.NEAREST,
        )
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()

    def close(self) -> None:
        """Close runtime resources."""
        state = self._state
        if state is None:
            return

        if hasattr(state.bus, "close"):
            with suppress(OSError):
                state.bus.close()
        self._state = None

    def _retry(self, func: Callable[[], T], context: str) -> T:
        """Run *func* with bounded retries for transient hardware faults.

        Calls ``_init_device()`` before each attempt so that the device is
        always in a known-good state when *func* runs.  On failure the bus is
        closed so the next attempt starts from a clean slate.
        """
        last_error: Exception | None = None

        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                self._init_device()  # no-op if already initialized
                return func()
            except DeviceError as err:
                last_error = err
            except Exception as err:  # pylint: disable=broad-exception-caught
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
    def _color_value(element: dict[str, Any]) -> int:
        """Return the Pillow fill value (0 = black, 1 = white) for an element.

        Reads the optional ``color`` key from the element dictionary.
        Accepts ``"black"`` for pixel-off (0) or any other value (including the
        default ``"white"``) for pixel-on (1).
        """
        return 0 if str(element.get("color", "white")).lower() == COLOR_BLACK else 1

    @staticmethod
    def _clamp_x(value: Any) -> int:
        """Clamp an x coordinate to display bounds."""
        return max(0, min(DISPLAY_WIDTH - 1, int(value)))

    @staticmethod
    def _clamp_y(value: Any) -> int:
        """Clamp a y coordinate to display bounds."""
        return max(0, min(DISPLAY_HEIGHT - 1, int(value)))
