"""Config flow for Big Brother 28."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import CONF_HOUSEMATES, CONF_START_DATE, DOMAIN


class BigBrother28ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Big Brother 28."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Big Brother 28",
                data={},
                options={
                    CONF_START_DATE: user_input[CONF_START_DATE],
                    CONF_HOUSEMATES: [],
                },
            )

        schema = vol.Schema({vol.Required(CONF_START_DATE): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return BigBrother28OptionsFlow(config_entry)


class BigBrother28OptionsFlow(config_entries.OptionsFlow):
    """Handle options — edit start date and housemate roster."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors: dict[str, str] = {}
        options = self.config_entry.options

        if user_input is not None:
            names = [
                n.strip()
                for n in user_input[CONF_HOUSEMATES].split(",")
                if n.strip()
            ]
            return self.async_create_entry(
                title="",
                data={
                    CONF_START_DATE: user_input[CONF_START_DATE],
                    CONF_HOUSEMATES: names,
                },
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_START_DATE, default=options.get(CONF_START_DATE, "")
                ): str,
                vol.Optional(
                    CONF_HOUSEMATES,
                    default=", ".join(options.get(CONF_HOUSEMATES, [])),
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
