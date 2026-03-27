"""Describe Argon Industria OLED events in the logbook."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
    LazyEventPartialState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    EVENT_BUS_EVENT,
    EVENT_DOUBLE_PRESS,
    EVENT_LONG_PRESS,
    EVENT_SINGLE_PRESS,
)

_PRESS_MESSAGES: dict[str, str] = {
    EVENT_SINGLE_PRESS: "Button single press",
    EVENT_DOUBLE_PRESS: "Button double press",
    EVENT_LONG_PRESS: "Button long press",
}


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[
        [str, str, Callable[[LazyEventPartialState], dict[str, Any]]], None
    ],
) -> None:
    """Register logbook descriptions for Argon Industria OLED button events."""

    @callback
    def _describe_button_event(event: LazyEventPartialState) -> dict[str, Any]:
        """Return a human-readable description for a button press event."""
        data = event.data
        event_type: str = data.get("type", "")
        message = _PRESS_MESSAGES.get(event_type, f"Button {event_type.replace('_', ' ')}")

        result: dict[str, Any] = {
            LOGBOOK_ENTRY_NAME: "Argon Industria OLED",
            LOGBOOK_ENTRY_MESSAGE: message,
        }

        # Link the entry to the button event entity so it shows up in the
        # entity's own Activity log alongside the standard state-change entries.
        if device_id := data.get("device_id"):
            ent_reg = er.async_get(hass)
            entity_id = next(
                (
                    entry.entity_id
                    for entry in er.async_entries_for_device(ent_reg, device_id)
                    if entry.domain == "event"
                ),
                None,
            )
            if entity_id:
                result[LOGBOOK_ENTRY_ENTITY_ID] = entity_id

        return result

    async_describe_event(DOMAIN, EVENT_BUS_EVENT, _describe_button_event)
