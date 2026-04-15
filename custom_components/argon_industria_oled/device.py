"""Hardware device layer for the Argon Industria OLED module."""

from __future__ import annotations

import io
import json
import logging
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from functools import cache, lru_cache
from pathlib import Path
from typing import Any, TypeVar

try:  # pragma: no cover - runtime import guard
    from smbus2 import SMBus
except ImportError as err:  # pragma: no cover - runtime import guard
    raise RuntimeError("smbus2 must be installed to use this integration") from err

try:  # pragma: no cover - runtime import guard
    from PIL import Image, ImageChops, ImageDraw, ImageFont
except ImportError as err:  # pragma: no cover - runtime import guard
    raise RuntimeError("Pillow must be installed to use this integration") from err

from .const import (
    COLOR_BLACK,
    COLOR_WHITE,
    DEFAULT_I2C_ADDRESS,
    DEFAULT_I2C_BUS,
    DISPLAY_HEIGHT,
    DISPLAY_WIDTH,
    ELEMENT_ARC,
    ELEMENT_CIRCLE,
    ELEMENT_DLIMG,
    ELEMENT_ELLIPSE,
    ELEMENT_ICON,
    ELEMENT_LINE,
    ELEMENT_MULTILINE,
    ELEMENT_PIESLICE,
    ELEMENT_PIXEL,
    ELEMENT_POLYGON,
    ELEMENT_PROGRESS_BAR,
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

# Map user-friendly anchor names to Pillow's two-character anchor codes.
# First character: horizontal (l=left, m=middle, r=right).
# Second character: vertical (t=top, m=middle, b=bottom) — for single-line text.
# multiline_text requires ascender/descender anchors (a/m/d); t→a and b→d are
# translated at call-time in the ELEMENT_MULTILINE branch below.
_ANCHOR_MAP: dict[str, str] = {
    "lt": "lt",
    "top-left": "lt",
    "topleft": "lt",
    "mt": "mt",
    "top-center": "mt",
    "topcenter": "mt",
    "top": "mt",
    "rt": "rt",
    "top-right": "rt",
    "topright": "rt",
    "lm": "lm",
    "middle-left": "lm",
    "left": "lm",
    "ml": "lm",
    "mm": "mm",
    "middle-center": "mm",
    "center": "mm",
    "middle": "mm",
    "rm": "rm",
    "middle-right": "rm",
    "right": "rm",
    "mr": "rm",
    "lb": "lb",
    "bottom-left": "lb",
    "bottomleft": "lb",
    "mb": "mb",
    "bottom-center": "mb",
    "bottom": "mb",
    "rb": "rb",
    "bottom-right": "rb",
    "bottomright": "rb",
}

# Material Design Icons assets bundled with the integration.
_ASSETS_DIR = Path(__file__).parent / "assets"
_MDI_FONT_PATH = _ASSETS_DIR / "materialdesignicons.ttf"
_MDI_META_PATH = _ASSETS_DIR / "materialdesignicons.meta.json"


@lru_cache(maxsize=1)
def _get_mdi_index() -> dict[str, str]:
    """Load and cache the MDI name/alias -> hex-codepoint mapping from meta.json.

    Supports both the optimized flat ``dict[str, str]`` format and the legacy
    list-of-entries format. Loaded once on first call; subsequent calls return
    the cached dict in O(1).
    Returns an empty dict and logs an error when the asset file is unreadable.
    """
    try:
        with _MDI_META_PATH.open(encoding="utf-8") as fh:
            raw_meta: Any = json.load(fh)
    except (OSError, json.JSONDecodeError) as err:
        _LOGGER.error("Failed to load materialdesignicons.meta.json: %s", err)
        return {}

    if isinstance(raw_meta, dict):
        return {
            name: codepoint
            for name, codepoint in raw_meta.items()
            if isinstance(name, str) and isinstance(codepoint, str)
        }

    if not isinstance(raw_meta, list):
        _LOGGER.error("Unexpected materialdesignicons.meta.json format: %s", type(raw_meta).__name__)
        return {}

    index: dict[str, str] = {}
    for entry in raw_meta:
        if not isinstance(entry, dict):
            continue

        name = entry.get("name")
        codepoint = entry.get("codepoint")
        if not isinstance(name, str) or not isinstance(codepoint, str):
            continue

        index[name] = codepoint
        aliases = entry.get("aliases", [])
        if isinstance(aliases, list):
            for alias in aliases:
                if isinstance(alias, str):
                    index.setdefault(alias, codepoint)
    return index


def _lookup_mdi_codepoint(icon_name: str) -> str | None:
    """Return the hex codepoint for *icon_name*, or ``None`` if not found."""
    return _get_mdi_index().get(icon_name)


@cache
def _load_mdi_font(size: int) -> ImageFont.FreeTypeFont:
    """Return the MDI TrueType font at *size*, loading it only once per size.

    ``lru_cache`` ensures the 1.3 MB TTF is parsed at most once per unique
    pixel size across the lifetime of the process.

    Raises ``DeviceError`` when the font file cannot be opened.
    """
    try:
        return ImageFont.truetype(str(_MDI_FONT_PATH), size)
    except OSError as err:
        raise DeviceError(f"Could not load MDI font: {err}") from err


def _render_mdi_glyph(codepoint: str, size: int) -> Image.Image | None:
    """Render an MDI glyph into a ``size x size`` 1-bit Pillow image.

    Returns ``None`` for blank/invisible glyphs (empty ink bounding box).

    MDI SVG viewports are square (24x24 units) but the TTF encoding is NOT:
    the horizontal advance equals ``size`` while the vertical ink range is only
    ~75-90% of ``size`` (cap-height / UPM ratio).  Naively stretching the raw
    ink bounding box to ``size x size`` would distort the icon proportions
    (e.g. the home icon's 24x18 px ink would be stretched 1.33x taller).

    Instead the glyph is scaled **uniformly** so its largest dimension fills
    ``size`` pixels, then centred on the ``size x size`` output canvas.
    All ink pixels remain within the declared square; the bounding-box
    contract is therefore fully maintained.
    """
    font = _load_mdi_font(size)
    glyph_char = chr(int(codepoint, 16))
    bb = font.getbbox(glyph_char)
    glyph_w = int(bb[2] - bb[0])
    glyph_h = int(bb[3] - bb[1])
    if glyph_w <= 0 or glyph_h <= 0:
        return None

    scratch = Image.new("L", (glyph_w, glyph_h), color=0)
    ImageDraw.Draw(scratch).text((int(-bb[0]), int(-bb[1])), glyph_char, font=font, fill=255)

    # Scale uniformly so the largest dimension fills ``size`` pixels exactly,
    # preserving the original aspect ratio (no distortion).
    scale = min(size / glyph_w, size / glyph_h)
    scaled_w = max(1, round(glyph_w * scale))
    scaled_h = max(1, round(glyph_h * scale))
    scaled = scratch.resize((scaled_w, scaled_h), resample=Image.Resampling.LANCZOS)

    # Centre the scaled glyph on a size x size canvas so the output always
    # occupies the declared square bounding box.
    output = Image.new("L", (size, size), color=0)
    offset_x = (size - scaled_w) // 2
    offset_y = (size - scaled_h) // 2
    output.paste(scaled, (offset_x, offset_y))

    return output.point(lambda p: 1 if p > 127 else 0, "1")


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

    def _draw_element(  # pylint: disable=too-many-locals,too-many-return-statements,too-many-branches,too-many-statements
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
            anchor = _ANCHOR_MAP.get(str(element.get("anchor", "lt")).lower(), "lt")
            raw_width = element.get("width")
            raw_height = element.get("height")
            if raw_width is not None and raw_height is not None:
                w = max(1, int(raw_width))
                h = max(1, int(raw_height))
                horiz = anchor[0]  # l / m / r
                vert = anchor[1]  # t / m / b
                tx = x if horiz == "l" else (x + w // 2 if horiz == "m" else x + w)
                ty = y if vert == "t" else (y + h // 2 if vert == "m" else y + h)
                drawer.text((tx, ty), value, font=font, fill=color, anchor=anchor)
            else:
                drawer.text((x, y), value, font=font, fill=color, anchor=anchor)
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
            _anchor = _ANCHOR_MAP.get(str(element.get("anchor", "lt")).lower(), "lt")
            # multiline_text uses ascender/descender vertical anchors (a/m/d), not top/bottom (t/b).
            anchor = _anchor[0] + {"t": "a", "b": "d"}.get(_anchor[1], _anchor[1])
            drawer.multiline_text(
                (x, y + offset_y), value, font=font, fill=color, spacing=spacing, anchor=anchor
            )
            return

        if element_type == ELEMENT_LINE:
            x1 = self._clamp_x(element.get("x_start", 0))
            y1 = self._clamp_y(element.get("y_start", 0))
            x2 = self._clamp_x(element.get("x_end", 0))
            y2 = self._clamp_y(element.get("y_end", y1))
            width = max(1, int(element.get("width", 1)))
            drawer.line((x1, y1, x2, y2), fill=color, width=width)
            return

        if element_type == ELEMENT_RECTANGLE:
            x1 = self._clamp_x(element.get("x_start", 0))
            y1 = self._clamp_y(element.get("y_start", 0))
            x2 = self._clamp_x(element.get("x_end", x1))
            y2 = self._clamp_y(element.get("y_end", y1))
            fill: int | None = color if bool(element.get("fill", False)) else None
            width = max(1, int(element.get("width", 1)))
            radius = max(0, int(element.get("radius", 0)))
            if radius > 0:
                drawer.rounded_rectangle(
                    (x1, y1, x2, y2), radius=radius, outline=color, fill=fill, width=width
                )
            else:
                drawer.rectangle((x1, y1, x2, y2), outline=color, fill=fill, width=width)
            return

        if element_type == ELEMENT_POLYGON:
            self._draw_polygon(drawer, element, color)
            return

        if element_type == ELEMENT_CIRCLE:
            self._draw_circle(drawer, element, color)
            return

        if element_type == ELEMENT_ELLIPSE:
            self._draw_ellipse(drawer, element, color)
            return

        if element_type in (ELEMENT_ARC, ELEMENT_PIESLICE):
            self._draw_arc_or_pieslice(drawer, element, color, element_type)
            return

        if element_type == ELEMENT_PIXEL:
            x = self._clamp_x(element.get("x", 0))
            y = self._clamp_y(element.get("y", 0))
            drawer.point((x, y), fill=color)
            return

        if element_type == ELEMENT_DLIMG:
            self._draw_image(canvas, element)
            return

        if element_type == ELEMENT_PROGRESS_BAR:
            self._draw_progress_bar(drawer, canvas, element)
            return

        if element_type == ELEMENT_ICON:
            self._draw_icon(canvas, element)
            return

    def _draw_polygon(
        self, drawer: ImageDraw.ImageDraw, element: dict[str, Any], color: int
    ) -> None:
        """Draw a polygon element.

        ``points`` is a flat list of coordinate values or a list of [x, y] pairs.
        Each coordinate supports pixels or a percentage string (e.g. ``"50%"``).
        ``fill: true`` fills the interior with *color*.
        ``width`` controls the outline thickness (default ``1``).
        """
        raw_points = element.get("points", [])
        flat: list[int] = []
        if raw_points and isinstance(raw_points[0], (list, tuple)):
            for pair in raw_points:
                flat.append(self._clamp_x(pair[0]))
                flat.append(self._clamp_y(pair[1]))
        else:
            for i, val in enumerate(raw_points):
                flat.append(self._clamp_x(val) if i % 2 == 0 else self._clamp_y(val))
        if len(flat) < 4:
            return
        fill: int | None = color if bool(element.get("fill", False)) else None
        width = max(1, int(element.get("width", 1)))
        drawer.polygon(flat, outline=color, fill=fill, width=width)

    def _draw_circle(
        self, drawer: ImageDraw.ImageDraw, element: dict[str, Any], color: int
    ) -> None:
        """Draw a circle element.

        ``x`` and ``y`` are the centre coordinates; ``radius`` is the circle radius.
        All three accept pixels or percentage strings.
        ``fill: true`` fills the circle; ``width`` controls outline thickness.
        """
        cx = self._clamp_x(element.get("x", 0))
        cy = self._clamp_y(element.get("y", 0))
        r = self._resolve_radius(element.get("radius", 10))
        x1, y1 = cx - r, cy - r
        x2, y2 = cx + r, cy + r
        fill: int | None = color if bool(element.get("fill", False)) else None
        width = max(1, int(element.get("width", 1)))
        drawer.ellipse((x1, y1, x2, y2), outline=color, fill=fill, width=width)

    def _draw_ellipse(
        self, drawer: ImageDraw.ImageDraw, element: dict[str, Any], color: int
    ) -> None:
        """Draw an ellipse element defined by its bounding box.

        ``x_start``, ``y_start``, ``x_end``, ``y_end`` mark the bounding box corners.
        All coordinates accept pixels or percentage strings.
        ``fill: true`` fills the ellipse; ``width`` controls outline thickness.
        """
        x1 = self._clamp_x(element.get("x_start", 0))
        y1 = self._clamp_y(element.get("y_start", 0))
        x2 = self._clamp_x(element.get("x_end", x1))
        y2 = self._clamp_y(element.get("y_end", y1))
        fill: int | None = color if bool(element.get("fill", False)) else None
        width = max(1, int(element.get("width", 1)))
        drawer.ellipse((x1, y1, x2, y2), outline=color, fill=fill, width=width)

    def _draw_arc_or_pieslice(  # pylint: disable=too-many-locals
        self,
        drawer: ImageDraw.ImageDraw,
        element: dict[str, Any],
        color: int,
        element_type: str,
    ) -> None:
        """Draw an arc or pie-slice element defined by a bounding box and angles.

        ``x_start``, ``y_start``, ``x_end``, ``y_end`` mark the bounding box.
        ``start`` and ``end`` are angles in degrees (0 = right, 90 = down) or
        percentage strings (``"25%"`` = 90°).
        All coordinates accept pixels or percentage strings.
        ``fill: true`` fills the pie slice (ignored for ``arc``).
        ``width`` controls the line thickness (default ``1``).
        """
        x1 = self._clamp_x(element.get("x_start", 0))
        y1 = self._clamp_y(element.get("y_start", 0))
        x2 = self._clamp_x(element.get("x_end", x1))
        y2 = self._clamp_y(element.get("y_end", y1))
        start = self._resolve_angle(element.get("start", 0))
        end = self._resolve_angle(element.get("end", 180))
        width = max(1, int(element.get("width", 1)))
        if element_type == ELEMENT_ARC:
            drawer.arc((x1, y1, x2, y2), start=start, end=end, fill=color, width=width)
        else:
            fill_color: int | None = color if bool(element.get("fill", False)) else None
            drawer.pieslice(
                (x1, y1, x2, y2), start=start, end=end, outline=color, fill=fill_color, width=width
            )

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

    def _draw_progress_bar(  # pylint: disable=too-many-locals
        self, drawer: ImageDraw.ImageDraw, canvas: Image.Image, element: dict[str, Any]
    ) -> None:
        """Draw a progress bar element onto the framebuffer.

        Renders in four ordered layers — background fill, progress fill, outline
        border, and an optional percentage label — then optionally centers a
        ``"<N>%"`` text label inside the bar.

        The percentage label is composited with XOR so each glyph pixel inverts the
        underlying bar pixel: the label appears **black** over the filled (bright)
        region and **white** over the empty (dark) region, making it always legible
        at any progress value without any extra configuration.

        Supported properties (all optional except the bounding box coordinates):

        * ``x_start``, ``y_start``, ``x_end``, ``y_end`` — bounding box (clamped).
        * ``progress`` — 0-100 float/int; values outside the range are clamped.
        * ``direction`` — fill direction: ``"right"`` (default), ``"left"``,
          ``"up"``, or ``"down"``.
        * ``background`` — background color (default ``"black"``).
        * ``fill`` — progress fill color (default ``"white"``).
        * ``outline`` — border color (default ``"white"``).
        * ``width`` — border thickness in pixels (default ``1``).
        * ``show_percentage`` — when truthy, draws a centered ``"<N>%"`` label
          using XOR compositing. ``size`` controls the font size (default ``8``).
        """
        x1 = self._clamp_x(element.get("x_start", 0))
        y1 = self._clamp_y(element.get("y_start", 0))
        x2 = self._clamp_x(element.get("x_end", x1))
        y2 = self._clamp_y(element.get("y_end", y1))
        progress = max(0.0, min(100.0, float(element.get("progress", 0))))
        direction = str(element.get("direction", "right")).lower()
        if direction not in {"right", "left", "up", "down"}:
            raise DeviceError(f"Invalid progress_bar direction: {direction!r}")

        bg_color = self._color_from_key(element, "background", COLOR_BLACK)
        fill_color = self._color_from_key(element, "fill", COLOR_WHITE)
        outline_color = self._color_from_key(element, "outline", COLOR_WHITE)
        border_width = max(1, int(element.get("width", 1)))

        # 1. Background
        drawer.rectangle((x1, y1, x2, y2), fill=bg_color)

        # 2. Progress fill
        if progress > 0.0:
            bar_w = x2 - x1
            bar_h = y2 - y1
            filled_w = int(bar_w * progress / 100.0)
            filled_h = int(bar_h * progress / 100.0)
            if direction == "right":
                drawer.rectangle((x1, y1, x1 + filled_w, y2), fill=fill_color)
            elif direction == "left":
                drawer.rectangle((x2 - filled_w, y1, x2, y2), fill=fill_color)
            elif direction == "down":
                drawer.rectangle((x1, y1, x2, y1 + filled_h), fill=fill_color)
            else:  # up
                drawer.rectangle((x1, y2 - filled_h, x2, y2), fill=fill_color)

        # 3. Outline border
        drawer.rectangle((x1, y1, x2, y2), outline=outline_color, width=border_width)

        # 4. Optional percentage text — XOR composited so the label always contrasts
        #    with its background: black glyphs over the filled region, white glyphs
        #    over the unfilled region, rendered pixel by pixel automatically.
        if bool(element.get("show_percentage", False)):
            font = self._load_font(element.get("size", 8))
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            # Render text onto a blank mask layer (white glyphs on black).
            text_layer = Image.new("1", canvas.size, color=0)
            ImageDraw.Draw(text_layer).text(
                (cx, cy), f"{int(progress)}%", font=font, fill=1, anchor="mm"
            )
            # XOR: canvas pixels under each glyph pixel are inverted in place.
            canvas.paste(ImageChops.logical_xor(canvas, text_layer))

    def _draw_icon(self, canvas: Image.Image, element: dict[str, Any]) -> None:
        """Draw a Material Design Icon onto the framebuffer.

        All ink pixels are guaranteed to fit within the ``size x size`` square
        whose top-left corner is at ``(x, y)``.  For example ``x=10``, ``y=20``,
        ``size=30`` confines the icon to the region ``(10, 20) -> (39, 49)``.
        The glyph is scaled uniformly (aspect ratio preserved) so its largest
        dimension fills ``size`` pixels, then centred within the square —
        no pixels escape the declared bounding box.

        * ``value`` — icon name, optionally prefixed with ``mdi:``
          (e.g. ``"mdi:home"`` or ``"home"``).  Required.
        * ``x``, ``y`` — top-left corner of the icon square (clamped).  Default ``0, 0``.
        * ``size`` — side length of the icon square in pixels (default ``24``).
        * ``fill`` — icon color; ``"black"`` or ``"white"`` (default ``"white"``).

        Raises ``DeviceError`` when the icon name is not found in the metadata.
        Returns silently when the glyph has no visible ink (blank codepoint).
        """
        raw_value = str(element.get("value", ""))
        icon_name = raw_value[4:] if raw_value.startswith("mdi:") else raw_value
        if not icon_name:
            raise DeviceError("icon element requires a non-empty 'value'")

        codepoint = _lookup_mdi_codepoint(icon_name)
        if codepoint is None:
            raise DeviceError(f"Unknown MDI icon: {icon_name!r}")

        size = max(6, int(element.get("size", 24)))
        x = self._clamp_x(element.get("x", 0))
        y = self._clamp_y(element.get("y", 0))
        fill = self._color_from_key(element, "fill", COLOR_WHITE)

        glyph_img = _render_mdi_glyph(codepoint, size)
        if glyph_img is None:
            return  # blank/invisible glyph — nothing to draw

        fill_img = Image.new("1", (size, size), color=fill)
        canvas.paste(fill_img, (x, y), mask=glyph_img)

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

        The 1-bit monochrome framebuffer is converted to grayscale and scaled 2x
        with nearest-neighbour resampling so the preview remains crisp and legible
        in the Home Assistant UI.
        """
        if self._state is None:
            return None
        image = self._state.framebuffer.convert("L").resize(
            (DISPLAY_WIDTH * 2, DISPLAY_HEIGHT * 2),
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
        return ArgonOledDevice._color_from_key(element, "color")

    @staticmethod
    def _color_from_key(element: dict[str, Any], key: str, default: str = COLOR_WHITE) -> int:
        """Return the Pillow fill value (0 = black, 1 = white) for a named color key.

        Accepts ``"black"`` for pixel-off (0) or any other value for pixel-on (1).
        ``default`` is used when *key* is absent from *element*.
        """
        return 0 if str(element.get(key, default)).lower() == COLOR_BLACK else 1

    @staticmethod
    def _resolve_radius(value: Any) -> int:
        """Resolve a radius value; accepts pixels or a ``"N%"`` string.

        Percentage is relative to ``min(DISPLAY_WIDTH, DISPLAY_HEIGHT)`` (= 64).
        """
        ref = min(DISPLAY_WIDTH, DISPLAY_HEIGHT)
        if isinstance(value, str):
            s = value.strip()
            if s.endswith("%"):
                return max(0, round(float(s[:-1]) / 100.0 * ref))
        return max(0, int(value))

    @staticmethod
    def _resolve_angle(value: Any) -> float:
        """Resolve an angle value; accepts degrees or a ``"N%"`` string (% of 360°)."""
        if isinstance(value, str):
            s = value.strip()
            if s.endswith("%"):
                return float(s[:-1]) / 100.0 * 360.0
        return float(value)

    @staticmethod
    def _clamp_x(value: Any) -> int:
        """Resolve and clamp an x coordinate; accepts pixels or a ``"N%"`` string."""
        if isinstance(value, str):
            s = value.strip()
            if s.endswith("%"):
                return max(0, min(DISPLAY_WIDTH - 1, round(float(s[:-1]) / 100.0 * DISPLAY_WIDTH)))
        return max(0, min(DISPLAY_WIDTH - 1, int(value)))

    @staticmethod
    def _clamp_y(value: Any) -> int:
        """Resolve and clamp a y coordinate; accepts pixels or a ``"N%"`` string."""
        if isinstance(value, str):
            s = value.strip()
            if s.endswith("%"):
                return max(
                    0, min(DISPLAY_HEIGHT - 1, round(float(s[:-1]) / 100.0 * DISPLAY_HEIGHT))
                )
        return max(0, min(DISPLAY_HEIGHT - 1, int(value)))
