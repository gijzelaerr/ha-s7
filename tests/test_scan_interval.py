"""The scan interval must stay positive: anything else polls the PLC in a tight loop."""

from __future__ import annotations

import probatio
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import InvalidData
from homeassistant.helpers import config_validation as cv
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.s7.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_RACK,
    CONF_SCAN_INTERVAL,
    CONF_SLOT,
    CONF_TAGS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

TAG = "DB1.DBD0:REAL"


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


@pytest.mark.parametrize("seconds", [-5, 0])
async def test_options_reject_a_non_positive_interval(hass: HomeAssistant, s7_server, seconds: int) -> None:
    entry = await _setup(hass, s7_server[1], [TAG])
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(result["flow_id"], {CONF_SCAN_INTERVAL: seconds, CONF_TAGS: TAG})
    await hass.config_entries.async_unload(entry.entry_id)


async def test_options_form_still_serializes(hass: HomeAssistant, s7_server) -> None:
    entry = await _setup(hass, s7_server[1], [TAG])
    result = await hass.config_entries.options.async_init(entry.entry_id)
    fields = probatio.to_field_list(result["data_schema"], custom_serializer=cv.custom_serializer)
    assert next(f for f in fields if f["name"] == CONF_SCAN_INTERVAL)["valueMin"] == 1
    await hass.config_entries.async_unload(entry.entry_id)


async def test_saved_negative_interval_uses_the_default(hass: HomeAssistant, s7_server) -> None:
    entry = await _setup(hass, s7_server[1], [TAG], **{CONF_SCAN_INTERVAL: -5})
    assert entry.runtime_data.update_interval == DEFAULT_SCAN_INTERVAL
    await hass.config_entries.async_unload(entry.entry_id)
