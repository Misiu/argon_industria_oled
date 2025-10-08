"""Coordinator for updating the Argon Industria OLED display."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.network import async_get_ipv4_addresses
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_LINE1_SENSOR,
    CONF_LINE1_SOURCE,
    CONF_LINE2_SENSOR,
    CONF_LINE2_SOURCE,
    COORDINATOR_UPDATE_INTERVAL,
    DEFAULT_LINE1_SOURCE,
    DEFAULT_LINE2_SOURCE,
    LINE_SOURCE_CPU_TEMPERATURE,
    LINE_SOURCE_IP_ADDRESS,
    LINE_SOURCE_SENSOR,
    MAX_LINE_LENGTH,
)
from .display import (
    ArgonIndustriaOledDisplay,
    DisplayCommunicationError,
    DisplayError,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class DisplayLineConfig:
    """Configuration for a single display line."""

    source: str
    sensor: str | None


class ArgonIndustriaOledCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Coordinate data updates for the Argon Industria OLED display."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Argon Industria OLED",
            update_interval=COORDINATOR_UPDATE_INTERVAL,
        )
        self._entry = entry
        self._display = ArgonIndustriaOledDisplay()
        self._executor_lock = asyncio.Lock()

    @property
    def entry(self) -> ConfigEntry:
        """Return the active config entry."""
        return self._entry

    def update_config_entry(self, entry: ConfigEntry) -> None:
        """Update the config entry reference for new options."""
        self._entry = entry

    async def _async_update_data(self) -> dict[str, str]:
        """Fetch and write the latest information to the display."""
        line_config = self._resolve_line_config()

        try:
            lines = await self._async_render_lines(line_config)
            await self._async_write_lines(lines)
        except DisplayCommunicationError as err:
            raise UpdateFailed(f"Failed to communicate with OLED: {err}") from err
        except DisplayError as err:
            raise UpdateFailed(f"Display error: {err}") from err

        return lines

    async def _async_render_lines(self, config: Mapping[str, DisplayLineConfig]) -> dict[str, str]:
        """Render each configured line to display text."""
        rendered: dict[str, str] = {}

        line1 = await self._async_render_line(config[CONF_LINE1_SOURCE])
        rendered["line1"] = line1

        line2 = await self._async_render_line(config[CONF_LINE2_SOURCE])
        rendered["line2"] = line2

        return rendered

    def _resolve_line_config(self) -> dict[str, DisplayLineConfig]:
        """Combine entry data and options into line configuration."""
        data: dict[str, Any] = {**self._entry.data, **self._entry.options}

        return {
            CONF_LINE1_SOURCE: DisplayLineConfig(
                source=data.get(CONF_LINE1_SOURCE, DEFAULT_LINE1_SOURCE),
                sensor=data.get(CONF_LINE1_SENSOR),
            ),
            CONF_LINE2_SOURCE: DisplayLineConfig(
                source=data.get(CONF_LINE2_SOURCE, DEFAULT_LINE2_SOURCE),
                sensor=data.get(CONF_LINE2_SENSOR),
            ),
        }

    async def _async_render_line(self, config: DisplayLineConfig) -> str:
        """Render a single display line based on its configuration."""
        if config.source == LINE_SOURCE_IP_ADDRESS:
            return await self._async_get_primary_ipv4()
        if config.source == LINE_SOURCE_CPU_TEMPERATURE:
            return await self._async_get_cpu_temperature()
        if config.source == LINE_SOURCE_SENSOR:
            return self._render_sensor_value(config.sensor)
        raise HomeAssistantError(f"Unsupported line source: {config.source}")

    async def _async_get_primary_ipv4(self) -> str:
        """Return the first active IPv4 address for the host."""
        addresses = [addr for addr in async_get_ipv4_addresses() if not addr.startswith("127.")]
        if not addresses:
            return "IP unavailable"
        return sorted(addresses)[0]

    async def _async_get_cpu_temperature(self) -> str:
        """Read the CPU temperature from the main thermal zone."""
        def read_temperature() -> str:
            path = "/sys/class/thermal/thermal_zone0/temp"
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    raw = handle.read().strip()
            except FileNotFoundError:
                raise HomeAssistantError("CPU temperature path not found") from None
            except OSError as err:
                raise HomeAssistantError(f"Unable to read CPU temperature: {err}") from err

            try:
                millidegrees = int(raw)
            except ValueError as err:
                raise HomeAssistantError("Invalid CPU temperature value") from err

            return f"CPU {millidegrees / 1000:.1f}°C"

        return await self.hass.async_add_executor_job(read_temperature)

    def _render_sensor_value(self, entity_id: str | None) -> str:
        """Return the state string for the selected sensor entity."""
        if not entity_id:
            return "Sensor not set"
        state = self.hass.states.get(entity_id)
        if state is None:
            return "Sensor unavailable"
        if state.state in ("unknown", "unavailable"):
            return state.state.title()
        unit = state.attributes.get("unit_of_measurement")
        value = state.state
        if unit:
            return f"{value} {unit}"[:MAX_LINE_LENGTH]
        return value[:MAX_LINE_LENGTH]

    async def _async_write_lines(self, lines: Mapping[str, str]) -> None:
        """Write prepared lines to the display, serialized in the executor."""
        async with self._executor_lock:
            await self.hass.async_add_executor_job(self._display.ensure_initialized)
            await self.hass.async_add_executor_job(
                self._display.show_lines,
                [lines.get("line1", ""), lines.get("line2", "")],
            )

    async def async_shutdown(self) -> None:
        """Release display resources."""
        await self.hass.async_add_executor_job(self._display.close)
