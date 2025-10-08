"""Config flow for the Argon Industria OLED integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_LINE1_SENSOR,
    CONF_LINE1_SOURCE,
    CONF_LINE2_SENSOR,
    CONF_LINE2_SOURCE,
    DEFAULT_LINE1_SOURCE,
    DEFAULT_LINE2_SOURCE,
    DOMAIN,
    LINE_SOURCE_SENSOR,
    LINE_SOURCES,
)
from .display import (
    ArgonIndustriaOledDisplay,
    DisplayCommunicationError,
    DisplayError,
    I2CDisabledError,
)


def _normalize_user_selection(data: Mapping[str, Any]) -> dict[str, Any]:
    """Sanitize and normalise user selections prior to storing."""
    normalized = dict(data)
    for sensor_field in (CONF_LINE1_SENSOR, CONF_LINE2_SENSOR):
        if not normalized.get(sensor_field):
            normalized.pop(sensor_field, None)
    return normalized


class ArgonIndustriaOledConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Argon Industria OLED integration."""

    VERSION = 1

    def __init__(self) -> None:
        self._display_validated = False

    async def async_step_user(self, user_input: Mapping[str, Any] | None = None) -> FlowResult:
        """Handle the initial step of the config flow."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if not self._display_validated:
            errors = await self._async_validate_display()
            if not errors:
                self._display_validated = True

        if user_input is not None and not errors:
            errors = self._validate_sensor_fields(user_input)
            if not errors:
                data = _normalize_user_selection(user_input)
                return self.async_create_entry(title="Argon Industria OLED", data=data)

        schema = self._build_schema(user_input)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_import(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml (not supported)."""
        return await self.async_step_user(user_input)

    async def _async_validate_display(self) -> dict[str, str]:
        """Validate that I²C is enabled and the OLED can be reached."""
        display = ArgonIndustriaOledDisplay()
        try:
            await self.hass.async_add_executor_job(display.ensure_initialized)
        except I2CDisabledError:
            return {"base": "i2c_disabled"}
        except DisplayCommunicationError:
            return {"base": "display_not_found"}
        except DisplayError:
            return {"base": "welcome_failed"}
        finally:
            await self.hass.async_add_executor_job(display.close)
        return {}

    def _validate_sensor_fields(self, data: Mapping[str, Any]) -> dict[str, str]:
        """Validate sensor-specific selections from the form."""
        errors: dict[str, str] = {}

        def validate_line(source_key: str, sensor_key: str) -> None:
            if data.get(source_key) != LINE_SOURCE_SENSOR:
                return
            sensor = data.get(sensor_key)
            if not sensor:
                errors[sensor_key] = "sensor_required"
                return
            if self.hass.states.get(sensor) is None:
                errors[sensor_key] = "sensor_not_found"

        validate_line(CONF_LINE1_SOURCE, CONF_LINE1_SENSOR)
        validate_line(CONF_LINE2_SOURCE, CONF_LINE2_SENSOR)

        return errors

    def _build_schema(self, user_input: Mapping[str, Any] | None) -> vol.Schema:
        """Build the data schema for the config flow form."""
        user_input = user_input or {}

        return vol.Schema(
            {
                vol.Required(CONF_LINE1_SOURCE, default=user_input.get(CONF_LINE1_SOURCE, DEFAULT_LINE1_SOURCE)): vol.In(LINE_SOURCES),
                vol.Optional(CONF_LINE1_SENSOR, default=user_input.get(CONF_LINE1_SENSOR, "")): str,
                vol.Required(CONF_LINE2_SOURCE, default=user_input.get(CONF_LINE2_SOURCE, DEFAULT_LINE2_SOURCE)): vol.In(LINE_SOURCES),
                vol.Optional(CONF_LINE2_SENSOR, default=user_input.get(CONF_LINE2_SENSOR, "")): str,
            }
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return ArgonIndustriaOledOptionsFlow(config_entry)


class ArgonIndustriaOledOptionsFlow(config_entries.OptionsFlow):
    """Handle options updates for the integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: Mapping[str, Any] | None = None) -> FlowResult:
        """Manage the options for the integration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = self._validate_sensor_fields(user_input)
            if not errors:
                data = _normalize_user_selection(user_input)
                return self.async_create_entry(title="Argon Industria OLED", data=data)

        schema = self._build_schema(user_input)
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

    def _build_schema(self, user_input: Mapping[str, Any] | None) -> vol.Schema:
        """Construct the options schema, defaulting to current settings."""
        current = {**self._config_entry.data, **self._config_entry.options}
        user_input = user_input or current

        return vol.Schema(
            {
                vol.Required(CONF_LINE1_SOURCE, default=user_input.get(CONF_LINE1_SOURCE, DEFAULT_LINE1_SOURCE)): vol.In(LINE_SOURCES),
                vol.Optional(CONF_LINE1_SENSOR, default=user_input.get(CONF_LINE1_SENSOR, "")): str,
                vol.Required(CONF_LINE2_SOURCE, default=user_input.get(CONF_LINE2_SOURCE, DEFAULT_LINE2_SOURCE)): vol.In(LINE_SOURCES),
                vol.Optional(CONF_LINE2_SENSOR, default=user_input.get(CONF_LINE2_SENSOR, "")): str,
            }
        )

    def _validate_sensor_fields(self, data: Mapping[str, Any]) -> dict[str, str]:
        """Validate sensor selections for the options flow."""
        errors: dict[str, str] = {}

        def validate_line(source_key: str, sensor_key: str) -> None:
            if data.get(source_key) != LINE_SOURCE_SENSOR:
                return
            sensor = data.get(sensor_key)
            if not sensor:
                errors[sensor_key] = "sensor_required"
                return
            if self.hass.states.get(sensor) is None:
                errors[sensor_key] = "sensor_not_found"

        validate_line(CONF_LINE1_SOURCE, CONF_LINE1_SENSOR)
        validate_line(CONF_LINE2_SOURCE, CONF_LINE2_SENSOR)

        return errors
