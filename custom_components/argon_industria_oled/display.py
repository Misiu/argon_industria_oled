"""Low-level routines for interacting with the Argon Industria OLED display."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

try:  # pragma: no cover - evaluated at runtime
    from smbus import SMBus  # provided by smbus-cffi
except ImportError as err:  # pragma: no cover - import guard
    raise RuntimeError(
        "smbus-cffi must be installed to use the Argon Industria OLED integration"
    ) from err

try:  # pragma: no cover - evaluated at runtime
    from PIL import Image, ImageDraw, ImageFont
except ImportError as err:  # pragma: no cover - import guard
    raise RuntimeError(
        "Pillow must be installed to use the Argon Industria OLED integration"
    ) from err

from .const import (
    DEFAULT_I2C_ADDRESS,
    DEFAULT_I2C_BUS,
    DISPLAY_HEIGHT,
    DISPLAY_PADDING,
    DISPLAY_WIDTH,
    MAX_LINE_LENGTH,
    WELCOME_LINES,
)

_COMMAND_CONTROL_BYTE = 0x00
_DATA_CONTROL_BYTE = 0x6A  # Matches OLED_SLAVEADDRESS from original script
_COLUMN_OFFSET = 2
_PAGE_HEIGHT = 8
_INIT_SEQUENCE: tuple[int, ...] = (
    0xAE,  # display off
    0xD5,
    0x80,  # clock divide ratio
    0xA8,
    0x3F,  # multiplex ratio (1/64 duty)
    0xD3,
    0x00,  # display offset
    0x40,  # display start line
    0xA1,  # segment remap
    0xC8,  # COM scan direction
    0xDA,
    0x12,  # COM pins hardware configuration
    0x81,
    0x7F,  # contrast control
    0xD9,
    0x22,  # pre-charge period
    0xDB,
    0x35,  # VCOMH deselect level
    0xA4,  # display resume
    0xA6,  # normal display
    0x8D,
    0x14,  # enable charge pump
    0xAF,  # display on
)
_PAGE_COUNT = DISPLAY_HEIGHT // _PAGE_HEIGHT
_WRITE_CHUNK = 16


class DisplayError(Exception):
    """Base class for OLED display errors."""


class I2CDisabledError(DisplayError):
    """Raised when the Raspberry Pi I²C bus is not available."""


class DisplayCommunicationError(DisplayError):
    """Raised when the integration cannot communicate with the display."""


@dataclass(slots=True)
class _DisplayState:
    """Hold the state objects backing the OLED display."""

    bus: SMBus
    font: ImageFont.ImageFont


class ArgonIndustriaOledDisplay:
    """Encapsulate all hardware access for the Argon Industria OLED."""

    def __init__(self, bus: int | None = None, address: int = DEFAULT_I2C_ADDRESS) -> None:
        self._bus_id = bus
        self._address = address
        self._state: _DisplayState | None = None

    def ensure_initialized(self) -> None:
        """Initialize the display if it is not already ready."""

        if self._state is not None:
            return

        # Auto-detect bus if not specified (try bus 1 first, then bus 0 for older versions)
        if self._bus_id is None:
            self._bus_id = self._detect_i2c_bus()

        self._ensure_i2c_enabled()

        try:
            bus = SMBus(self._bus_id)
        except FileNotFoundError as err:
            raise I2CDisabledError(
                f"I2C bus {self._bus_id} is not enabled (missing /dev/i2c-{self._bus_id})."
            ) from err
        except OSError as err:
            raise DisplayCommunicationError(f"Unable to open I2C bus {self._bus_id}: {err}") from err

        try:
            self._write_commands(bus, _INIT_SEQUENCE)
        except DisplayCommunicationError:
            if hasattr(bus, "close"):
                try:
                    bus.close()
                except OSError:
                    pass
            raise

        font = ImageFont.load_default()
        self._state = _DisplayState(bus=bus, font=font)
        try:
            self.display_welcome()
        except DisplayError:
            self.close()
            raise

    def _detect_i2c_bus(self) -> int:
        """Detect available I2C bus, trying bus 1 first then bus 0."""
        # Try bus 1 (default for Raspberry Pi 5 and newer models)
        if Path(f"/dev/i2c-{DEFAULT_I2C_BUS}").exists():
            return DEFAULT_I2C_BUS
        # Try bus 0 (older Raspberry Pi models)
        if Path("/dev/i2c-0").exists():
            return 0
        # No I2C bus found
        raise I2CDisabledError(
            "I2C is not enabled on this system. "
            "For Home Assistant OS, install the HassOS I2C Configurator add-on: "
            "https://community.home-assistant.io/t/add-on-hassos-i2c-configurator/264167"
        )

    def _ensure_i2c_enabled(self) -> None:
        """Verify that the Linux I²C device file exists."""

        i2c_path = Path(f"/dev/i2c-{self._bus_id}")
        if not i2c_path.exists():
            raise I2CDisabledError(
                f"I2C bus {self._bus_id} is not enabled (missing {i2c_path}). "
                "For Home Assistant OS, install the HassOS I2C Configurator add-on: "
                "https://community.home-assistant.io/t/add-on-hassos-i2c-configurator/264167"
            )

    def display_welcome(self) -> None:
        """Show a welcome message on the OLED display."""

        self.show_lines(WELCOME_LINES)

    def show_lines(self, lines: Sequence[str]) -> None:
        """Render the provided lines on the display."""

        state = self._state
        if state is None:
            raise DisplayCommunicationError("Display is not initialised")

        image = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT))
        drawer = ImageDraw.Draw(image)
        drawer.rectangle((0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT), outline=0, fill=0)

        _, top, _, bottom = state.font.getbbox("A")
        line_height = bottom - top
        # Defensive: line_height should always be > 0 for a valid font and character.
        assert line_height > 0, f"Unexpected non-positive line_height: {line_height}"
        y = DISPLAY_PADDING
        for line in list(lines)[: DISPLAY_HEIGHT // line_height]:
            drawer.text((DISPLAY_PADDING, y), line[:MAX_LINE_LENGTH], font=state.font, fill=1)
            y += line_height + DISPLAY_PADDING

        self._write_image(state.bus, image)

    def _write_image(self, bus: SMBus, image: Image.Image) -> None:
        """Write an image buffer to the SH1106 display controller."""

        pixels = image.load()
        for page in range(_PAGE_COUNT):
            try:
                self._write_commands(
                    bus,
                    (
                        0xB0 + page,
                        (_COLUMN_OFFSET & 0x0F),
                        0x10 | ((_COLUMN_OFFSET >> 4) & 0x0F),
                    ),
                )
            except DisplayCommunicationError as err:
                raise DisplayCommunicationError(f"Failed to address OLED page {page}: {err}") from err

            page_data: list[int] = []
            for column in range(DISPLAY_WIDTH):
                byte = 0
                for bit in range(_PAGE_HEIGHT):
                    y = page * _PAGE_HEIGHT + bit
                    if pixels[column, y]:
                        byte |= 1 << bit
                page_data.append(byte)

            self._write_data(bus, page_data)

    def _write_commands(self, bus: SMBus, commands: Iterable[int]) -> None:
        """Send a sequence of command bytes to the controller."""

        for command in commands:
            try:
                bus.write_byte_data(self._address, _COMMAND_CONTROL_BYTE, command & 0xFF)
            except OSError as err:
                raise DisplayCommunicationError(
                    f"Failed to write OLED command 0x{command:02X}: {err}"
                ) from err

    def _write_data(self, bus: SMBus, data: Sequence[int]) -> None:
        """Write pixel data to the display in safe chunk sizes."""

        for index in range(0, len(data), _WRITE_CHUNK):
            chunk = list(data[index : index + _WRITE_CHUNK])
            try:
                bus.write_i2c_block_data(self._address, _DATA_CONTROL_BYTE, chunk)
            except OSError as err:
                raise DisplayCommunicationError(f"Failed to write OLED data: {err}") from err

    def close(self) -> None:
        """Release display resources."""

        if self._state is None:
            return

        bus = self._state.bus
        if hasattr(bus, "close"):
            try:
                bus.close()
            except OSError:
                # Best effort close; nothing we can do at this point.
                pass
        self._state = None
