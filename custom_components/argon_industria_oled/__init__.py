"""Home Assistant setup for the Argon Industria OLED integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_CLEAR,
    ATTR_PAYLOAD,
    DOMAIN,
    PLATFORMS,
    SERVICE_CLEAR,
    SERVICE_DRAW_CUSTOM,
    SERVICE_SHOW_LOGO,
)
from .coordinator import ArgonIndustriaOledCoordinator
from .device import DeviceError

_LOGGER = logging.getLogger(__name__)

INTEGRATION_CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)  # pylint: disable=invalid-name

DRAW_CUSTOM_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CLEAR, default=True): bool,
        vol.Required(ATTR_PAYLOAD): list,
    },
    extra=vol.PREVENT_EXTRA,
)


def _get_active_coordinator(hass: HomeAssistant) -> ArgonIndustriaOledCoordinator | None:
    """Return the active single-entry coordinator, if available."""
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        return None
    return next(iter(entries.values()))


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up integration-wide services."""
    del config
    hass.data.setdefault(DOMAIN, {})

    async def async_handle_drawcustom(call: ServiceCall) -> None:
        coordinator = _get_active_coordinator(hass)
        if coordinator is None:
            _LOGGER.warning("No active Argon Industria OLED config entry")
            return

        clear = bool(call.data.get(ATTR_CLEAR, True))
        elements = call.data.get(ATTR_PAYLOAD) or []
        if not elements:
            _LOGGER.error("drawcustom requires non-empty 'payload'")
            return
        try:
            await coordinator.async_draw(elements=elements, clear=clear)
        except DeviceError as err:
            _LOGGER.error("drawcustom failed: %s", err)

    async def async_handle_clear(call: ServiceCall) -> None:
        del call
        coordinator = _get_active_coordinator(hass)
        if coordinator is None:
            _LOGGER.warning("No active Argon Industria OLED config entry")
            return

        try:
            await coordinator.async_clear()
        except DeviceError as err:
            _LOGGER.error("clear failed: %s", err)

    async def async_handle_show_logo(call: ServiceCall) -> None:
        del call
        coordinator = _get_active_coordinator(hass)
        if coordinator is None:
            _LOGGER.warning("No active Argon Industria OLED config entry")
            return

        try:
            await coordinator.async_show_startup()
        except DeviceError as err:
            _LOGGER.error("show_logo failed: %s", err)

    if not hass.services.has_service(DOMAIN, SERVICE_DRAW_CUSTOM):
        hass.services.async_register(
            DOMAIN,
            SERVICE_DRAW_CUSTOM,
            async_handle_drawcustom,
            schema=DRAW_CUSTOM_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_CLEAR):
        hass.services.async_register(DOMAIN, SERVICE_CLEAR, async_handle_clear)

    if not hass.services.has_service(DOMAIN, SERVICE_SHOW_LOGO):
        hass.services.async_register(DOMAIN, SERVICE_SHOW_LOGO, async_handle_show_logo)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Argon Industria OLED from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    coordinator = ArgonIndustriaOledCoordinator(hass, entry)

    try:
        await coordinator.async_initialize()
        await coordinator.async_show_startup()
        await coordinator.async_config_entry_first_refresh()
    except DeviceError as err:
        raise ConfigEntryNotReady(f"OLED setup failed: {err}") from err

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    coordinator: ArgonIndustriaOledCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
    await coordinator.async_shutdown()

    if not hass.data[DOMAIN]:
        if hass.services.has_service(DOMAIN, SERVICE_DRAW_CUSTOM):
            hass.services.async_remove(DOMAIN, SERVICE_DRAW_CUSTOM)
        if hass.services.has_service(DOMAIN, SERVICE_CLEAR):
            hass.services.async_remove(DOMAIN, SERVICE_CLEAR)
        if hass.services.has_service(DOMAIN, SERVICE_SHOW_LOGO):
            hass.services.async_remove(DOMAIN, SERVICE_SHOW_LOGO)

    return True
