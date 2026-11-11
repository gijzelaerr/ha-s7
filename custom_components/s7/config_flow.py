"""Config flow for the s7 integration."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

import probatio as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from . import async_move_plc_id
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
PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

_CONNECTION_FIELDS: dict[vol.Marker, Any] = {
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_RACK, default=DEFAULT_RACK): int,
    vol.Optional(CONF_SLOT, default=DEFAULT_SLOT): int,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    vol.Optional(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): vol.In(PROTOCOL_CHOICES),
    vol.Optional(CONF_USE_TLS, default=False): bool,
    vol.Optional(CONF_PASSWORD): PASSWORD_SELECTOR,
}
_CONNECTION_KEYS = frozenset(str(key) for key in _CONNECTION_FIELDS)

STEP_USER_SCHEMA = vol.Schema({**_CONNECTION_FIELDS, vol.Optional(CONF_TAGS): TAGS_SELECTOR})
STEP_RECONFIGURE_SCHEMA = vol.Schema(_CONNECTION_FIELDS)


def split_tags(raw: str) -> list[str]:
    """Split a tag list on newlines or semicolons.

    Commas are not separators: nodeS7 addresses (``DB1,R0``) contain them.
    """
    return list(dict.fromkeys(t.strip() for t in re.split(r"[\n;]", raw) if t.strip()))


def _blocking_test_read(connection: Mapping[str, Any], tags: list[str]) -> tuple[str | None, str]:
    """Connect over a throwaway connection and read the tags once.

    Returns ``(None, "")`` when it worked, ``("cannot_connect", "")`` when the
    PLC did not accept the connection, and ``("cannot_read_tag", names)`` when
    it did but the named tags could not be read.
    """
    parsed = _parse_tags_for_validation(tags)
    client = create_client(
        connection.get(CONF_PROTOCOL, DEFAULT_PROTOCOL),
        host=connection[CONF_HOST],
        rack=connection.get(CONF_RACK, DEFAULT_RACK),
        slot=connection.get(CONF_SLOT, DEFAULT_SLOT),
        port=connection.get(CONF_PORT, DEFAULT_PORT),
        use_tls=connection.get(CONF_USE_TLS, False),
        password=connection.get(CONF_PASSWORD),
    )
    try:
        try:
            client.connect()
        except Exception as err:
            _LOGGER.warning("PLC connection test failed: %s", err)
            return "cannot_connect", ""
        if not parsed:
            return None, ""
        try:
            client.read_tags(list(parsed.values()))
        except Exception as err:
            _LOGGER.warning("PLC test read failed: %s", err)
        else:
            return None, ""
        # A read of several tags fails as a whole, so ask for each tag on its
        # own to find the ones the PLC refuses.
        failed: list[str] = []
        for name, tag in parsed.items():
            if not client.connected:  # a refused read can end the session
                try:
                    client.connect()
                except Exception as err:  # the PLC is gone: not the fault of a tag
                    _LOGGER.warning("PLC connection was lost during the test read: %s", err)
                    return "cannot_connect", ""
            try:
                client.read_tags([tag])
            except Exception as err:
                _LOGGER.warning("PLC test read of %s failed: %s", name, err)
                failed.append(name)
        return "cannot_read_tag", ", ".join(failed or parsed)
    finally:
        try:
            if client.connected:
                client.disconnect()
        except Exception as err:
            _LOGGER.debug("Closing the test connection failed: %s", err)


async def async_test_read(hass: HomeAssistant, connection: Mapping[str, Any], tags: list[str]) -> tuple[str | None, str]:
    """Run the test read in the executor; see ``_blocking_test_read``."""
    return await hass.async_add_executor_job(_blocking_test_read, connection, tags)


class S7ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Siemens S7 PLC."""

    VERSION = 1
    MINOR_VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}

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
                error, failed_tags = await async_test_read(self.hass, user_input, tags)
                if error:
                    errors["base"] = error
                    placeholders["tag"] = failed_tags
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
            description_placeholders=placeholders,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Change how the PLC is reached; the tags and their entities stay.

        The form opens with the stored settings, the password included (the
        field masks it). Emptying the password field removes the password.
        """
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}

        if user_input is not None:
            tags: list[str] = entry.options.get(CONF_TAGS, entry.data.get(CONF_TAGS, []))
            try:
                _parse_tags_for_validation(tags)
            except ValueError:  # stored before such a tag was refused; Configure reports it
                tags = []
            error, failed_tags = await async_test_read(self.hass, user_input, tags)
            if error:
                errors["base"] = error
                placeholders["tag"] = failed_tags
            else:
                data = {k: v for k, v in entry.data.items() if k not in _CONNECTION_KEYS} | user_input
                old_id, new_id = plc_id(entry.data), plc_id(data)
                other = self.hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, new_id)
                if other is not None and other.entry_id != entry.entry_id:
                    return self.async_abort(reason="already_configured")
                if new_id != old_id:
                    # Unique IDs and the device are built from the PLC id. Without
                    # this the reload would drop every entity and make new ones.
                    async_move_plc_id(self.hass, entry, old_id, new_id)
                title = entry.title
                if title == f"S7 {entry.data[CONF_HOST]}":
                    title = f"S7 {data[CONF_HOST]}"
                if entry.update_listeners:  # loaded: its update listener reloads it
                    return self.async_update_and_abort(entry, unique_id=new_id, title=title, data=data)
                return self.async_update_reload_and_abort(entry, unique_id=new_id, title=title, data=data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(STEP_RECONFIGURE_SCHEMA, user_input or entry.data),
            errors=errors,
            description_placeholders=placeholders,
        )

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
        placeholders: dict[str, str] = {}
        shown_tags = "\n".join(self._entry.options.get(CONF_TAGS, self._entry.data.get(CONF_TAGS, [])))

        if user_input is not None:
            shown_tags = user_input.get(CONF_TAGS, "") or ""
            tags = split_tags(shown_tags)
            try:
                _parse_tags_for_validation(tags)
            except ValueError as err:
                errors["base"] = "invalid_tags"
                _LOGGER.warning("Tag validation failed: %s", err)
            else:
                error, failed_tags = await async_test_read(self.hass, self._entry.data, tags)
                if error:
                    errors["base"] = error
                    placeholders["tag"] = failed_tags
                else:
                    return self.async_create_entry(
                        title="",
                        data={CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL], CONF_TAGS: tags},
                    )

        current = self._entry.options.get(CONF_SCAN_INTERVAL, int(DEFAULT_SCAN_INTERVAL.total_seconds()))
        # The tags are a suggested value, not a default: a default is filled
        # back in when the box is emptied, so the last tag could not be removed.
        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=current): vol.All(int, vol.Range(min=1)),
                vol.Optional(CONF_TAGS): TAGS_SELECTOR,
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, {CONF_TAGS: shown_tags}),
            errors=errors,
            description_placeholders=placeholders,
        )
