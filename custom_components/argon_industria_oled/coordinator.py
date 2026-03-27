"""Runtime manager for the Argon Industria OLED device."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .button_monitor import ButtonMonitor
from .const import (
    CONF_SCREEN_TIMEOUT,
    DEFAULT_I2C_ADDRESS,
    DEFAULT_I2C_BUS,
    DEFAULT_SCREEN_TIMEOUT,
)
from .device import ArgonOledDevice, DeviceError

if TYPE_CHECKING:
    from datetime import datetime

_LOGGER = logging.getLogger(__name__)


class ArgonIndustriaOledCoordinator:
    """Manage the OLED device lifecycle, display operations, and button events.

    This is a plain runtime manager — not a polling coordinator.  It serializes
    I²C access through an asyncio lock and owns the button monitor thread.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.device = ArgonOledDevice(
            bus=entry.data.get("bus", DEFAULT_I2C_BUS),
            address=entry.data.get("address", DEFAULT_I2C_ADDRESS),
        )
        self._executor_lock = asyncio.Lock()
        self._cancel_timeout: CALLBACK_TYPE | None = None
        self._display_active: bool = False
        self._button_monitor: ButtonMonitor | None = None
        self._button_callbacks: list[Callable[[str], None]] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_initialize(self) -> None:
        """Initialize the I²C device and start the GPIO button monitor."""
        async with self._executor_lock:
            await self.hass.async_add_executor_job(self.device.initialize)

        self._button_monitor = ButtonMonitor(self._handle_button_event)
        _LOGGER.debug("Starting button monitor")
        started = await self.hass.async_add_executor_job(self._button_monitor.start)
        if started:
            _LOGGER.info("Button monitoring started")
        else:
            _LOGGER.info(
                "Button monitoring unavailable (gpiod not installed or no compatible GPIO chip)"
            )

    async def async_shutdown(self) -> None:
        """Stop the button monitor and release hardware resources."""
        self._async_cancel_timeout()
        if self._button_monitor is not None:
            _LOGGER.debug("Stopping button monitor")
            await self.hass.async_add_executor_job(self._button_monitor.stop)
        await self.hass.async_add_executor_job(self.device.close)

    # ------------------------------------------------------------------
    # Button event subscription
    # ------------------------------------------------------------------

    def subscribe_button_event(self, cb: Callable[[str], None]) -> Callable[[], None]:
        """Subscribe *cb* to button press events.

        Returns an unsubscribe callable.  Pass it to
        ``Entity.async_on_remove`` so the subscription is cleaned up
        automatically when the entity is removed.
        """
        self._button_callbacks.append(cb)
        _LOGGER.debug("Button callback registered: %s", cb)

        def unsubscribe() -> None:
            with suppress(ValueError):
                self._button_callbacks.remove(cb)
            _LOGGER.debug("Button callback unregistered: %s", cb)

        return unsubscribe

    def _handle_button_event(self, event_type: str) -> None:
        """Receive a press event from the monitor thread and dispatch to the HA loop."""
        _LOGGER.debug("Button event from monitor thread: %r", event_type)
        for cb in list(self._button_callbacks):
            self.hass.loop.call_soon_threadsafe(cb, event_type)

    # ------------------------------------------------------------------
    # Display operations
    # ------------------------------------------------------------------

    async def async_show_startup(self) -> None:
        """Render the startup splash screen."""
        async with self._executor_lock:
            await self.hass.async_add_executor_job(self.device.show_startup)
        self._display_active = True
        self._async_schedule_timeout()

    async def async_draw(self, elements: list[dict[str, Any]], clear: bool) -> None:
        """Draw custom elements and schedule the inactivity timeout."""
        async with self._executor_lock:
            await self.hass.async_add_executor_job(self.device.draw, elements, clear)
        self._display_active = True
        self._async_schedule_timeout()

    async def async_clear(self) -> None:
        """Clear the display and cancel any pending inactivity timeout."""
        async with self._executor_lock:
            await self.hass.async_add_executor_job(self.device.clear)
        self._display_active = False
        self._async_cancel_timeout()

    # ------------------------------------------------------------------
    # Screen timeout
    # ------------------------------------------------------------------

    def async_update_timeout(self, seconds: int) -> None:
        """Apply a new timeout value; restarts the timer only when the display is active."""
        if self._display_active:
            self._async_schedule_timeout(seconds)

    def _async_schedule_timeout(self, seconds: int | None = None) -> None:
        """Start (or restart) the inactivity clear timer."""
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
        """Handle expiry of the inactivity timer."""
        self._cancel_timeout = None
        self.hass.async_create_task(self._async_timeout_clear())

    async def _async_timeout_clear(self) -> None:
        """Clear the display when the inactivity timeout fires."""
        _LOGGER.debug("Screen timeout reached - clearing display")
        try:
            await self.async_clear()
        except DeviceError as err:
            _LOGGER.warning("Timeout auto-clear failed: %s", err)

    def _async_cancel_timeout(self) -> None:
        """Cancel the pending inactivity timer."""
        if self._cancel_timeout is not None:
            self._cancel_timeout()
            self._cancel_timeout = None

    async def async_entry_updated(self, _hass: HomeAssistant, entry: ConfigEntry) -> None:
        """React to options updates (e.g. a new screen timeout from the options flow)."""
        timeout = int(
            entry.options.get(
                CONF_SCREEN_TIMEOUT,
                entry.data.get(CONF_SCREEN_TIMEOUT, DEFAULT_SCREEN_TIMEOUT),
            )
        )
        self.async_update_timeout(timeout)

