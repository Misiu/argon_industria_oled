"""Data coordinator for Argon Industria OLED device state."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    COORDINATOR_UPDATE_INTERVAL,
    STATE_CONNECTED,
    STATE_LAST_DRAW_TIME,
    STATE_LAST_ERROR,
)
from .device import ArgonOledDevice, DeviceError

_LOGGER = logging.getLogger(__name__)


class ArgonIndustriaOledCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Track OLED connectivity and last operation status."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name="Argon Industria OLED",
            update_interval=COORDINATOR_UPDATE_INTERVAL,
        )
        self.entry = entry
        self.device = ArgonOledDevice()
        self._executor_lock = asyncio.Lock()

    async def _async_update_data(self) -> dict[str, Any]:
        """Refresh connectivity state without crashing the integration."""
        connected = await self.hass.async_add_executor_job(self.device.probe)

        return {
            STATE_CONNECTED: connected,
            STATE_LAST_ERROR: None if connected else "display_not_found",
            STATE_LAST_DRAW_TIME: self.data.get(STATE_LAST_DRAW_TIME) if self.data else None,
        }

    async def async_initialize(self) -> None:
        """Initialize the device."""
        async with self._executor_lock:
            await self.hass.async_add_executor_job(self.device.initialize)
        await self.async_set_status(connected=True, error=None)

    async def async_show_startup(self) -> None:
        """Show splash screen and keep it visible."""
        async with self._executor_lock:
            await self.hass.async_add_executor_job(self.device.initialize)
            await self.hass.async_add_executor_job(self.device.show_startup)
        await self.async_set_status(connected=True, error=None, drew=True)

    async def async_draw(self, elements: list[dict[str, Any]], clear: bool) -> None:
        """Draw custom elements and update status."""
        try:
            async with self._executor_lock:
                await self.hass.async_add_executor_job(self.device.initialize)
                await self.hass.async_add_executor_job(self.device.draw, elements, clear)
        except DeviceError as err:
            _LOGGER.error("Draw failed: %s", err)
            await self.async_set_status(connected=False, error=str(err))
            raise

        await self.async_set_status(connected=True, error=None, drew=True)

    async def async_clear(self) -> None:
        """Clear display and update status."""
        try:
            async with self._executor_lock:
                await self.hass.async_add_executor_job(self.device.initialize)
                await self.hass.async_add_executor_job(self.device.clear)
        except DeviceError as err:
            _LOGGER.error("Clear failed: %s", err)
            await self.async_set_status(connected=False, error=str(err))
            raise

        await self.async_set_status(connected=True, error=None, drew=True)

    async def async_set_status(
        self, connected: bool, error: str | None, drew: bool = False
    ) -> None:
        """Persist service-operation health to coordinator data."""
        current = self.data or {
            STATE_CONNECTED: False,
            STATE_LAST_ERROR: None,
            STATE_LAST_DRAW_TIME: None,
        }
        updated = dict(current)
        updated[STATE_CONNECTED] = connected
        updated[STATE_LAST_ERROR] = error
        if drew:
            updated[STATE_LAST_DRAW_TIME] = self._current_iso_time()

        self.async_set_updated_data(updated)

    async def async_shutdown(self) -> None:
        """Close hardware resources."""
        await self.hass.async_add_executor_job(self.device.close)

    @staticmethod
    def _current_iso_time() -> str:
        """Return UTC timestamp string for diagnostics."""
        return datetime.now(UTC).isoformat()
