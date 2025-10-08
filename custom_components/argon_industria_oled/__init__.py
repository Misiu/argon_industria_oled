"""Home Assistant integration setup for the Argon Industria OLED module."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import ArgonIndustriaOledCoordinator

_LOGGER = logging.getLogger(__name__)

ConfigEntryType = ConfigEntry


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration from YAML (not supported)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntryType) -> bool:
    """Set up Argon Industria OLED from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = ArgonIndustriaOledCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntryType) -> bool:
    """Unload a config entry."""
    coordinator = hass.data[DOMAIN].pop(entry.entry_id)
    await coordinator.async_shutdown()
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntryType) -> None:
    """Handle options update."""
    coordinator: ArgonIndustriaOledCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.update_config_entry(entry)
    await coordinator.async_request_refresh()
