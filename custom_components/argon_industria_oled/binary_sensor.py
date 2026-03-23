"""Binary sensor entities for Argon Industria OLED."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEFAULT_I2C_ADDRESS,
    DEFAULT_I2C_BUS,
    DISPLAY_HEIGHT,
    DISPLAY_WIDTH,
    DOMAIN,
    STATE_CONNECTED,
)
from .coordinator import ArgonIndustriaOledCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensor platform from config entry."""
    coordinator: ArgonIndustriaOledCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ArgonOledConnectedBinarySensor(coordinator, entry)])


class ArgonOledConnectedBinarySensor(CoordinatorEntity[ArgonIndustriaOledCoordinator], BinarySensorEntity):
    """Report whether the OLED can be reached."""

    _attr_has_entity_name = True
    _attr_name = "Connected"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ArgonIndustriaOledCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_connected"

    @property
    def is_on(self) -> bool:
        """Return current device connectivity."""
        return bool((self.coordinator.data or {}).get(STATE_CONNECTED, False))

    @property
    def available(self) -> bool:
        """Entity remains available so diagnostics are visible even when disconnected."""
        return True

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return diagnostic details from coordinator state."""
        data = self.coordinator.data or {}
        return {
            "last_error": data.get("last_error"),
            "last_draw_time": data.get("last_draw_time"),
        }

    @property
    def device_info(self) -> dict:
        """Describe the physical OLED module for the device registry."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Argon Industria OLED",
            "manufacturer": "Argon40",
            "model": "Argon ONE V5 Industria OLED",
            "configuration_url": "https://argon40.com/products/argon-one-v5-industria-oled-module",
            "sw_version": "0.1.0",
            "hw_version": f"I2C {DEFAULT_I2C_BUS}@0x{DEFAULT_I2C_ADDRESS:02X} {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}",
        }
