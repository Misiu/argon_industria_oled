"""Diagnostic sensor entities for Argon Industria OLED."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_SCREEN_TIMEOUT,
    DEFAULT_I2C_ADDRESS,
    DEFAULT_I2C_BUS,
    DEFAULT_SCREEN_TIMEOUT,
    DISPLAY_HEIGHT,
    DISPLAY_WIDTH,
    DOMAIN,
)
from .coordinator import ArgonIndustriaOledCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up diagnostic sensors from config entry."""
    coordinator: ArgonIndustriaOledCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ArgonOledScreenTimeoutSensor(coordinator, entry)])


class _BaseDiagnosticSensor(CoordinatorEntity[ArgonIndustriaOledCoordinator], SensorEntity):
    """Shared entity behavior for static diagnostics."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ArgonIndustriaOledCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Describe the physical OLED module for the device registry."""
        hw_version = (
            f"I2C {DEFAULT_I2C_BUS}@0x{DEFAULT_I2C_ADDRESS:02X} {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}"
        )
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Argon Industria OLED",
            "manufacturer": "Argon40",
            "model": "Argon ONE V5 Industria OLED",
            "configuration_url": "https://argon40.com/products/argon-one-v5-industria-oled-module",
            "sw_version": "0.1.0",
            "hw_version": hw_version,
        }


class ArgonOledScreenTimeoutSensor(_BaseDiagnosticSensor):
    """Expose the configured screen-off timeout (read-only; edit via integration options)."""

    _attr_name = "Screen timeout"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(self, coordinator: ArgonIndustriaOledCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_screen_timeout"

    @property
    def native_value(self) -> int:
        """Return the configured screen timeout in seconds (0 = disabled)."""
        return int(
            self._entry.options.get(
                CONF_SCREEN_TIMEOUT,
                self._entry.data.get(CONF_SCREEN_TIMEOUT, DEFAULT_SCREEN_TIMEOUT),
            )
        )
