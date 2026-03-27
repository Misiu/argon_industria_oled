"""Pytest fixtures for drawcustom element rendering tests."""

from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from tests.drawcustom.helpers import DISPLAY_HEIGHT, DISPLAY_WIDTH, ArgonOledDevice


@pytest.fixture
def device() -> ArgonOledDevice:
    """Return an ArgonOledDevice instance without initializing I²C."""
    dev: ArgonOledDevice = object.__new__(ArgonOledDevice)
    dev._state = None  # pylint: disable=protected-access
    return dev


@pytest.fixture
def black_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """Return a blank (all-black) 128x64 1-bit image and its draw handle."""
    image = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=0)
    return image, ImageDraw.Draw(image)


@pytest.fixture
def white_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """Return an all-white 128x64 1-bit image and its draw handle."""
    image = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=1)
    return image, ImageDraw.Draw(image)
