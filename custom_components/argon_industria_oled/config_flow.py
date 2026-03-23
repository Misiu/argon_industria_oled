"""Config flow for Argon Industria OLED integration."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_I2C_ADDRESS, DEFAULT_I2C_BUS, DOMAIN, UNIQUE_ID
from .device import ArgonOledDevice, DeviceInitializeError, DeviceNotFoundError


class ArgonIndustriaOledConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle automatic setup of the OLED module."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Detect OLED immediately and create entry without user input."""
        del user_input
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(UNIQUE_ID)
        self._abort_if_unique_id_configured()

        display = ArgonOledDevice(bus=DEFAULT_I2C_BUS, address=DEFAULT_I2C_ADDRESS)

        try:
            found = await self.hass.async_add_executor_job(display.probe)
            if not found:
                return self.async_abort(reason="display_not_found")
        except DeviceNotFoundError:
            return self.async_abort(reason="display_not_found")
        except DeviceInitializeError:
            return self.async_abort(reason="cannot_initialize_display")
        except Exception:  # noqa: BLE001
            return self.async_abort(reason="unknown")
        finally:
            await self.hass.async_add_executor_job(display.close)

        return self.async_create_entry(
            title="Argon Industria OLED",
            data={
                "bus": DEFAULT_I2C_BUS,
                "address": DEFAULT_I2C_ADDRESS,
            },
        )
