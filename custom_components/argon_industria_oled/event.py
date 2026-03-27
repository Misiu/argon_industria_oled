"""Event entity for the Argon Industria OLED physical button."""

from __future__ import annotations

import logging

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    EVENT_BUS_EVENT,
    EVENT_DOUBLE_PRESS,
    EVENT_LONG_PRESS,
    EVENT_SINGLE_PRESS,
)
from .coordinator import ArgonIndustriaOledCoordinator
from .helpers import build_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the button event entity from a config entry."""
    coordinator: ArgonIndustriaOledCoordinator = entry.runtime_data
    async_add_entities([ArgonButtonEventEntity(coordinator, entry)])


class ArgonButtonEventEntity(EventEntity):
    """Represent the physical button on the Argon Industria OLED module.

    Fires one of three event types when the button is pressed:

    - ``single_press``: short tap
    - ``double_press``: two quick taps
    - ``long_press``: held press

    Each press also fires ``argon_industria_oled_event`` on the HA event bus
    with ``device_id`` and ``type`` so that ``device_trigger.py`` can expose
    device automations in the automation UI.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "button"
    _attr_device_class = EventDeviceClass.BUTTON

    def __init__(self, coordinator: ArgonIndustriaOledCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_button"
        self._attr_event_types = [EVENT_SINGLE_PRESS, EVENT_DOUBLE_PRESS, EVENT_LONG_PRESS]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info so this entity is grouped with the OLED device."""
        return build_device_info(self._entry)

    async def async_added_to_hass(self) -> None:
        """Register button callback when entity joins HA."""
        self.async_on_remove(self._coordinator.subscribe_button_event(self._handle_button_event))
        _LOGGER.debug("Button event entity registered (unique_id=%s)", self.unique_id)

    @callback
    def _handle_button_event(self, event_type: str) -> None:
        """Handle a button press event dispatched from the monitor thread."""
        _LOGGER.debug("Button event %r received (entity=%s)", event_type, self.entity_id)

        # Update EventEntity state — shown in entity history and logbook.
        self._trigger_event(event_type)
        self.async_write_ha_state()

        # Fire on the HA event bus so device_trigger.py can attach automations.
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
            {"device_id": device.id, "type": event_type},
        )
