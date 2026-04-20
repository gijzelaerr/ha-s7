"""Config flow for the s7 integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RACK,
    CONF_SCAN_INTERVAL,
    CONF_SLOT,
    CONF_TAGS,
    CONF_USE_TLS,
    DEFAULT_PORT,
    DEFAULT_RACK,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLOT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_RACK, default=DEFAULT_RACK): int,
        vol.Optional(CONF_SLOT, default=DEFAULT_SLOT): int,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_USE_TLS, default=False): bool,
        vol.Optional(CONF_PASSWORD): str,
        vol.Optional(CONF_TAGS, default=""): str,
    }
)


class S7ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Siemens S7 PLC."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            tags_raw: str = user_input.get(CONF_TAGS, "") or ""
            tags = [t.strip() for t in tags_raw.replace("\n", ",").split(",") if t.strip()]

            # Validate connection by attempting a connect in executor
            valid = await self._test_connection(user_input, tags)
            if not valid:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"{host}:{user_input[CONF_PORT]}")
                self._abort_if_unique_id_configured()

                data = dict(user_input)
                data[CONF_TAGS] = tags
                return self.async_create_entry(title=f"S7 {host}", data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def _test_connection(self, user_input: dict[str, Any], tags: list[str]) -> bool:
        """Attempt a throwaway connection to the PLC."""
        from s7 import Client

        def _try() -> bool:
            client = Client()
            try:
                client.connect(
                    user_input[CONF_HOST],
                    user_input.get(CONF_RACK, DEFAULT_RACK),
                    user_input.get(CONF_SLOT, DEFAULT_SLOT),
                    user_input.get(CONF_PORT, DEFAULT_PORT),
                    use_tls=user_input.get(CONF_USE_TLS, False),
                    password=user_input.get(CONF_PASSWORD),
                )
                if tags:
                    client.read_tags(tags)
                client.disconnect()
                return True
            except Exception as err:
                _LOGGER.warning("PLC connection test failed: %s", err)
                return False

        return await self.hass.async_add_executor_job(_try)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return S7OptionsFlow(config_entry)


class S7OptionsFlow(OptionsFlow):
    """Handle options (e.g., scan interval)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._entry.options.get(CONF_SCAN_INTERVAL, int(DEFAULT_SCAN_INTERVAL.total_seconds()))
        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=current): int,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
