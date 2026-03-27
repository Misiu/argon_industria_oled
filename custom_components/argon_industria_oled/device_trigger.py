"""Device triggers for the Argon Industria OLED physical button.

Exposes ``single_press``, ``double_press``, and ``long_press`` as device
automation triggers in the Home Assistant automation UI.

Each trigger attaches to the ``argon_industria_oled_event`` bus event and
filters by ``device_id`` and ``type`` so that automations only fire for the
correct device and press type.
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, EVENT_BUS_EVENT, EVENT_DOUBLE_PRESS, EVENT_LONG_PRESS, EVENT_SINGLE_PRESS

TRIGGER_TYPES = {EVENT_SINGLE_PRESS, EVENT_DOUBLE_PRESS, EVENT_LONG_PRESS}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict]:
    """Return the list of device triggers for an Argon Industria OLED device."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if not device or not any(identifier[0] == DOMAIN for identifier in device.identifiers):
        return []

    return [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: trigger_type,
        }
        for trigger_type in TRIGGER_TYPES
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> event_trigger.CALLBACK_TYPE:
    """Attach a trigger that fires when the matching button press event arrives."""
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: EVENT_BUS_EVENT,
            event_trigger.CONF_EVENT_DATA: {
                "device_id": config[CONF_DEVICE_ID],
                "type": config[CONF_TYPE],
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
