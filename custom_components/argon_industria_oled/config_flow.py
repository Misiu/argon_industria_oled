"""Config flow for Argon Industria OLED integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_SCREEN_TIMEOUT,
    DEFAULT_SCREEN_TIMEOUT,
    DOMAIN,
    UNIQUE_ID,
)
from .device import ArgonOledDevice, DeviceInitializeError, DeviceNotFoundError

_TIMEOUT_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=0,
        max=3600,
        step=1,
        unit_of_measurement="s",
        mode=selector.NumberSelectorMode.BOX,
    )
)


class ArgonIndustriaOledConfigFlow(  # pylint: disable=abstract-method
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Handle setup of the OLED module."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show form to configure timeout and detect the OLED display."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(UNIQUE_ID)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}

        if user_input is not None:
            display = ArgonOledDevice()
            try:
                found = await self.hass.async_add_executor_job(display.probe)
                if not found:
                    errors["base"] = "display_not_found"
                else:
                    return self.async_create_entry(
                        title="Argon Industria OLED",
                        data={
                            CONF_SCREEN_TIMEOUT: int(user_input[CONF_SCREEN_TIMEOUT]),
                        },
                    )
            except DeviceNotFoundError:
                errors["base"] = "display_not_found"
            except DeviceInitializeError:
                errors["base"] = "cannot_initialize_display"
            finally:
                await self.hass.async_add_executor_job(display.close)

        suggested = (
            user_input.get(CONF_SCREEN_TIMEOUT, DEFAULT_SCREEN_TIMEOUT)
            if user_input
            else DEFAULT_SCREEN_TIMEOUT
        )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_SCREEN_TIMEOUT, default=float(suggested)): _TIMEOUT_SELECTOR}
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(_config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return ArgonIndustriaOledOptionsFlow()


class ArgonIndustriaOledOptionsFlow(config_entries.OptionsFlow):
    """Handle option updates for the Argon Industria OLED integration."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show form to reconfigure the screen timeout."""
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_SCREEN_TIMEOUT: int(user_input[CONF_SCREEN_TIMEOUT])}
            )

        current = self.config_entry.options.get(
            CONF_SCREEN_TIMEOUT,
            self.config_entry.data.get(CONF_SCREEN_TIMEOUT, DEFAULT_SCREEN_TIMEOUT),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Required(CONF_SCREEN_TIMEOUT, default=float(current)): _TIMEOUT_SELECTOR}
            ),
        )
