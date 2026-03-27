"""Tests for the _color_value helper in ArgonOledDevice."""

from __future__ import annotations

from tests.drawcustom.helpers import make_device


def test_default_is_white() -> None:
    """Omitting the ``color`` key returns 1 (white)."""
    dev = make_device()
    assert dev._color_value({}) == 1  # pylint: disable=protected-access


def test_explicit_white() -> None:
    dev = make_device()
    assert dev._color_value({"color": "white"}) == 1  # pylint: disable=protected-access


def test_explicit_black() -> None:
    dev = make_device()
    assert dev._color_value({"color": "black"}) == 0  # pylint: disable=protected-access


def test_case_insensitive_black() -> None:
    dev = make_device()
    assert dev._color_value({"color": "BLACK"}) == 0  # pylint: disable=protected-access


def test_case_insensitive_white() -> None:
    dev = make_device()
    assert dev._color_value({"color": "White"}) == 1  # pylint: disable=protected-access


def test_unknown_value_defaults_to_white() -> None:
    """Any value other than 'black' is treated as white."""
    dev = make_device()
    assert dev._color_value({"color": "red"}) == 1  # pylint: disable=protected-access
