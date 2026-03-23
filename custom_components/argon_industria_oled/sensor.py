"""Diagnostic sensor entities for Argon Industria OLED."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_I2C_ADDRESS, DISPLAY_HEIGHT, DISPLAY_WIDTH, DOMAIN
from .coordinator import ArgonIndustriaOledCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up diagnostic sensors from config entry."""
    coordinator: ArgonIndustriaOledCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ArgonOledAddressSensor(coordinator, entry),
            ArgonOledResolutionSensor(coordinator, entry),
        ]
    )


class _BaseDiagnosticSensor(CoordinatorEntity[ArgonIndustriaOledCoordinator], SensorEntity):
    """Shared entity behavior for static diagnostics."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ArgonIndustriaOledCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Link sensor entities to the OLED device."""
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}


class ArgonOledAddressSensor(_BaseDiagnosticSensor):
    """Expose OLED I2C address for diagnostics."""

    _attr_name = "Address"

    def __init__(self, coordinator: ArgonIndustriaOledCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_address"

    @property
    def native_value(self) -> str:
        """Return fixed OLED I2C address."""
        return f"0x{DEFAULT_I2C_ADDRESS:02X}"


class ArgonOledResolutionSensor(_BaseDiagnosticSensor):
    """Expose OLED resolution for diagnostics."""

    _attr_name = "Resolution"

    def __init__(self, coordinator: ArgonIndustriaOledCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_resolution"

    @property
    def native_value(self) -> str:
        """Return fixed OLED resolution."""
        return f"{DISPLAY_WIDTH}x{DISPLAY_HEIGHT}"
