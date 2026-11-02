"""A tag that can never be read is refused when it is entered."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.s7.const import CONF_HOST, CONF_PORT, CONF_RACK, CONF_SCAN_INTERVAL, CONF_SLOT, CONF_TAGS, DOMAIN
from custom_components.s7.coordinator import parse_tags


async def _setup(hass: HomeAssistant, port: int, tags: list[str], **options) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1", CONF_RACK: 0, CONF_SLOT: 0, CONF_PORT: port, CONF_TAGS: tags},
        options=options,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.parametrize("tag", ["DB1.DBB0:STRING", "DB1.DBW0:S5TIME", "DB1.DBW0:BOGUS"])
def test_parse_tags_rejects_a_type_without_a_size(tag: str) -> None:
    with pytest.raises(ValueError, match="Unknown S7 type"):
        parse_tags([tag])


def test_parse_tags_keeps_a_string_with_a_length() -> None:
    assert parse_tags(["DB1.DBB0:STRING[10]"])["DB1.DBB0:STRING[10]"].size == 12


async def test_options_flow_reports_it(hass: HomeAssistant, s7_server) -> None:
    entry = await _setup(hass, s7_server[1], ["DB1.DBD0:REAL"])
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 30, CONF_TAGS: "DB1.DBB0:STRING"}
    )
    assert result["errors"] == {"base": "invalid_tags"}
    await hass.config_entries.async_unload(entry.entry_id)
