"""Config flow for the s7 integration."""

from __future__ import annotations

import logging
import re
from typing import Any

import probatio as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig

from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_RACK,
    CONF_SCAN_INTERVAL,
    CONF_SLOT,
    CONF_TAGS,
    CONF_USE_TLS,
    DEFAULT_PORT,
    DEFAULT_PROTOCOL,
    DEFAULT_RACK,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLOT,
    DOMAIN,
    PROTOCOL_CHOICES,
    plc_id,
)
from .coordinator import parse_tags as _parse_tags_for_validation
from .plc import create_client

_LOGGER = logging.getLogger(__name__)

# A multi-line box: pasted tags keep their line breaks, which a plain ``str``
# field drops, joining every tag into one unparseable address (#61).
TAGS_SELECTOR = TextSelector(TextSelectorConfig(multiline=True))

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_RACK, default=DEFAULT_RACK): int,
        vol.Optional(CONF_SLOT, default=DEFAULT_SLOT): int,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): vol.In(PROTOCOL_CHOICES),
        vol.Optional(CONF_USE_TLS, default=False): bool,
        vol.Optional(CONF_PASSWORD): str,
        vol.Optional(CONF_TAGS): TAGS_SELECTOR,
    }
)


def split_tags(raw: str) -> list[str]:
    """Split a tag list on newlines or semicolons.

    Commas are not separators: nodeS7 addresses (``DB1,R0``) contain them.
    """
    return list(dict.fromkeys(t.strip() for t in re.split(r"[\n;]", raw) if t.strip()))


class S7ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Siemens S7 PLC."""

    VERSION = 1
    MINOR_VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            tags_raw: str = user_input.get(CONF_TAGS, "") or ""
            tags = split_tags(tags_raw)

            try:
                _parse_tags_for_validation(tags)
            except ValueError as err:
                errors["base"] = "invalid_tags"
                _LOGGER.warning("Tag validation failed: %s", err)
            else:
                valid = await self._test_connection(user_input, tags)
                if not valid:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(plc_id(user_input))
                    self._abort_if_unique_id_configured()

                    data = dict(user_input)
                    data[CONF_TAGS] = tags
                    return self.async_create_entry(title=f"S7 {host}", data=data)

        # After an error, show the form again with what was entered, so a wrong
        # port does not also cost the tag list (#61). The password is not echoed.
        suggested = {k: v for k, v in (user_input or {}).items() if k != CONF_PASSWORD}
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_SCHEMA, suggested),
            errors=errors,
        )

    async def _test_connection(self, user_input: dict[str, Any], tags: list[str]) -> bool:
        """Attempt a throwaway connection to the PLC."""
        # Tags were already validated via _parse_tags_for_validation; reuse
        # that output so read_tags() sees Tag objects (supports nodeS7).
        parsed = _parse_tags_for_validation(tags) if tags else {}

        def _try() -> bool:
            client = create_client(
                user_input.get(CONF_PROTOCOL, DEFAULT_PROTOCOL),
                host=user_input[CONF_HOST],
                rack=user_input.get(CONF_RACK, DEFAULT_RACK),
                slot=user_input.get(CONF_SLOT, DEFAULT_SLOT),
                port=user_input.get(CONF_PORT, DEFAULT_PORT),
                use_tls=user_input.get(CONF_USE_TLS, False),
                password=user_input.get(CONF_PASSWORD),
            )
            try:
                client.connect()
                if parsed:
                    client.read_tags(list(parsed.values()))
                return True
            except Exception as err:
                _LOGGER.warning("PLC connection test failed: %s", err)
                return False
            finally:
                try:
                    if client.connected:
                        client.disconnect()
                except Exception as err:
                    _LOGGER.debug("Closing the test connection failed: %s", err)

        return await self.hass.async_add_executor_job(_try)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return S7OptionsFlow(config_entry)


class S7OptionsFlow(OptionsFlow):
    """Edit the scan interval and tag list of an existing entry."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        current_tags: list[str] = self._entry.options.get(CONF_TAGS, self._entry.data.get(CONF_TAGS, []))

        if user_input is not None:
            tags = split_tags(user_input.get(CONF_TAGS, "") or "")
            try:
                _parse_tags_for_validation(tags)
            except ValueError as err:
                errors["base"] = "invalid_tags"
                _LOGGER.warning("Tag validation failed: %s", err)
                current_tags = tags
            else:
                return self.async_create_entry(
                    title="",
                    data={CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL], CONF_TAGS: tags},
                )

        current = self._entry.options.get(CONF_SCAN_INTERVAL, int(DEFAULT_SCAN_INTERVAL.total_seconds()))
        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=current): vol.All(int, vol.Range(min=1)),
                vol.Optional(CONF_TAGS, default="\n".join(current_tags)): TAGS_SELECTOR,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
