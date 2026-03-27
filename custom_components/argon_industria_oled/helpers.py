"""Shared helpers for the Argon Industria OLED integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DEFAULT_I2C_ADDRESS, DEFAULT_I2C_BUS, DISPLAY_HEIGHT, DISPLAY_WIDTH, DOMAIN


def build_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return a consistent ``DeviceInfo`` for all entities in this integration.

    Hardware version is derived from the config entry so it reflects the actual
    bus and address used, rather than compile-time defaults.
    """
    bus: int = entry.data.get("bus", DEFAULT_I2C_BUS)
    address: int = entry.data.get("address", DEFAULT_I2C_ADDRESS)
    hw_version = f"I2C {bus}@0x{address:02X} {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}"
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Argon Industria OLED",
        manufacturer="Argon40",
        model="Argon ONE V5 Industria OLED",
        configuration_url="https://argon40.com/products/argon-one-v5-industria-oled-module",
        hw_version=hw_version,
    )
