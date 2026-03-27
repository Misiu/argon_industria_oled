"""Event entity for the Argon Industria OLED physical button."""

from __future__ import annotations

import logging

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DEFAULT_I2C_ADDRESS,
    DEFAULT_I2C_BUS,
    DISPLAY_HEIGHT,
    DISPLAY_WIDTH,
    DOMAIN,
    EVENT_BUS_EVENT,
    EVENT_DOUBLE_PRESS,
    EVENT_LONG_PRESS,
    EVENT_SINGLE_PRESS,
)
from .coordinator import ArgonIndustriaOledCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the button event entity from a config entry."""
    _LOGGER.debug("Setting up button event entity for entry %s", entry.entry_id)
    coordinator: ArgonIndustriaOledCoordinator = hass.data[DOMAIN][entry.entry_id]
    entity = ArgonButtonEventEntity(entry)
    async_add_entities([entity])
    coordinator.set_button_event_callback(entity.fire_button_event)
    _LOGGER.debug("Button event entity registered (unique_id=%s)", entity.unique_id)


class ArgonButtonEventEntity(EventEntity):
    """Represent the physical button on the Argon Industria OLED module.

    Fires one of three event types when the button is pressed:
    - ``single_press``: short tap
    - ``double_press``: two quick taps
    - ``long_press``: held for >= 0.6 s
    """

    _attr_has_entity_name = True
    _attr_translation_key = "button"
    _attr_device_class = EventDeviceClass.BUTTON

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_button"
        self._attr_event_types = [EVENT_SINGLE_PRESS, EVENT_DOUBLE_PRESS, EVENT_LONG_PRESS]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info so the entity is grouped with the OLED device."""
        hw_version = (
            f"I2C {DEFAULT_I2C_BUS}@0x{DEFAULT_I2C_ADDRESS:02X} {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}"
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Argon Industria OLED",
            manufacturer="Argon40",
            model="Argon ONE V5 Industria OLED",
            configuration_url="https://argon40.com/products/argon-one-v5-industria-oled-module",
            sw_version="0.1.0",
            hw_version=hw_version,
        )

    def fire_button_event(self, event_type: str) -> None:
        """Fire a button event. Must be called from the HA event loop."""
        _LOGGER.info(
            "Firing button event: %r (entity=%s)",
            event_type,
            self.entity_id,
        )
        self._trigger_event(event_type)
        self.async_write_ha_state()
        _LOGGER.debug("Button event %r written to state", event_type)

        # Also fire on the HA event bus so device triggers can attach.
        registry = dr.async_get(self.hass)
        device = registry.async_get_device(identifiers={(DOMAIN, self._entry.entry_id)})
        if device is None:
            _LOGGER.warning(
                "Device not found in registry for entry %s; "
                "device trigger bus event will not be fired",
                self._entry.entry_id,
            )
            return
        self.hass.bus.async_fire(
            EVENT_BUS_EVENT,
            {
                "device_id": device.id,
                "type": event_type,
            },
        )
