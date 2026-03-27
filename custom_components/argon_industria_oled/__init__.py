"""Home Assistant setup for the Argon Industria OLED integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError, ServiceValidationError
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

type ArgonIndustriaOledConfigEntry = ConfigEntry[ArgonIndustriaOledCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

DRAW_CUSTOM_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CLEAR, default=True): bool,
        vol.Required(ATTR_PAYLOAD): list,
    },
    extra=vol.PREVENT_EXTRA,
)


def _get_active_coordinator(hass: HomeAssistant) -> ArgonIndustriaOledCoordinator:
    """Return the active coordinator or raise ``ServiceValidationError``."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="no_active_entry",
    )


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register integration-wide services (called once at HA startup)."""
    del config

    async def async_handle_drawcustom(call: ServiceCall) -> None:
        coordinator = _get_active_coordinator(hass)
        elements: list[Any] = call.data.get(ATTR_PAYLOAD) or []
        if not elements:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="empty_payload",
            )
        clear = bool(call.data.get(ATTR_CLEAR, True))
        try:
            await coordinator.async_draw(elements=elements, clear=clear)
        except DeviceError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="draw_failed",
            ) from err

    async def async_handle_clear(call: ServiceCall) -> None:
        del call
        coordinator = _get_active_coordinator(hass)
        try:
            await coordinator.async_clear()
        except DeviceError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="clear_failed",
            ) from err

    async def async_handle_show_logo(call: ServiceCall) -> None:
        del call
        coordinator = _get_active_coordinator(hass)
        try:
            await coordinator.async_show_startup()
        except DeviceError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="show_logo_failed",
            ) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_DRAW_CUSTOM,
        async_handle_drawcustom,
        schema=DRAW_CUSTOM_SCHEMA,
    )
    hass.services.async_register(DOMAIN, SERVICE_CLEAR, async_handle_clear)
    hass.services.async_register(DOMAIN, SERVICE_SHOW_LOGO, async_handle_show_logo)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ArgonIndustriaOledConfigEntry) -> bool:
    """Set up Argon Industria OLED from a config entry."""
    coordinator = ArgonIndustriaOledCoordinator(hass, entry)

    try:
        await coordinator.async_initialize()
        await coordinator.async_show_startup()
    except DeviceError as err:
        raise ConfigEntryNotReady(f"OLED setup failed: {err}") from err

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(coordinator.async_entry_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ArgonIndustriaOledConfigEntry) -> bool:
    """Unload a config entry and release hardware resources."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    await entry.runtime_data.async_shutdown()
    return True
