"""Data coordinator for Argon Industria OLED device state."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_SCREEN_TIMEOUT,
    COORDINATOR_UPDATE_INTERVAL,
    DEFAULT_SCREEN_TIMEOUT,
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
        self._cancel_timeout: CALLBACK_TYPE | None = None
        self._display_active: bool = False

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
        self._display_active = True
        await self.async_set_status(connected=True, error=None, drew=True)
        self._async_schedule_timeout()

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

        self._display_active = True
        await self.async_set_status(connected=True, error=None, drew=True)
        self._async_schedule_timeout()

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

        self._display_active = False
        self._async_cancel_timeout()
        await self.async_set_status(connected=True, error=None, drew=True)

    def async_update_timeout(self, seconds: int) -> None:
        """Update screen timeout; restart timer only when the display is currently active."""
        if self._display_active:
            self._async_schedule_timeout(seconds)

    def _async_schedule_timeout(self, seconds: int | None = None) -> None:
        """Start or restart the inactivity clear timer."""
        self._async_cancel_timeout()
        if seconds is None:
            seconds = int(
                self.entry.options.get(
                    CONF_SCREEN_TIMEOUT,
                    self.entry.data.get(CONF_SCREEN_TIMEOUT, DEFAULT_SCREEN_TIMEOUT),
                )
            )
        if seconds > 0:
            self._cancel_timeout = async_call_later(self.hass, seconds, self._handle_timeout)

    @callback
    def _handle_timeout(self, _now: datetime) -> None:
        """Handle screen timeout expiry by scheduling an async display clear."""
        self._cancel_timeout = None
        self.hass.async_create_task(self._async_timeout_clear())

    async def _async_timeout_clear(self) -> None:
        """Clear the display after the inactivity timeout fires."""
        _LOGGER.debug("Screen timeout reached, clearing display")
        try:
            await self.async_clear()
        except DeviceError as err:
            _LOGGER.warning("Timeout auto-clear failed: %s", err)

    def _async_cancel_timeout(self) -> None:
        """Cancel the pending inactivity timer if one is scheduled."""
        if self._cancel_timeout is not None:
            self._cancel_timeout()
            self._cancel_timeout = None

    async def async_entry_updated(self, _hass: HomeAssistant, entry: ConfigEntry) -> None:
        """React to config entry option updates (e.g. from the options flow)."""
        timeout = int(
            entry.options.get(
                CONF_SCREEN_TIMEOUT,
                entry.data.get(CONF_SCREEN_TIMEOUT, DEFAULT_SCREEN_TIMEOUT),
            )
        )
        self.async_update_timeout(timeout)
        # Push a data update so coordinator entities (e.g. the timeout sensor) refresh immediately.
        if self.data is not None:
            self.async_set_updated_data(self.data)

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
        self._async_cancel_timeout()
        await self.hass.async_add_executor_job(self.device.close)

    @staticmethod
    def _current_iso_time() -> str:
        """Return UTC timestamp string for diagnostics."""
        return datetime.now(UTC).isoformat()
