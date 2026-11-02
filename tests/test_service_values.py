"""write_tag and pulse_tag look at the tag's type."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.s7.const import CONF_HOST, CONF_PORT, CONF_RACK, CONF_SLOT, CONF_TAGS, DOMAIN


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


@pytest.mark.parametrize("value", ["on", "123", "1.5", "hello"])
async def test_string_tag_keeps_the_text(hass: HomeAssistant, s7_server, value: str) -> None:
    tag = "DB2.DBB0:STRING[20]"
    entry = await _setup(hass, s7_server[1], [tag])
    await hass.services.async_call(DOMAIN, "write_tag", {"entry_id": entry.entry_id, "tag": tag, "value": value}, blocking=True)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN][entry.entry_id].data[tag] == value
    await hass.config_entries.async_unload(entry.entry_id)


async def test_numeric_tag_still_converts(hass: HomeAssistant, s7_server) -> None:
    tag = "DB2.DBW40:INT"
    entry = await _setup(hass, s7_server[1], [tag])
    await hass.services.async_call(DOMAIN, "write_tag", {"entry_id": entry.entry_id, "tag": tag, "value": "123"}, blocking=True)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN][entry.entry_id].data[tag] == 123
    await hass.config_entries.async_unload(entry.entry_id)


async def test_pulse_refuses_a_non_bool_tag(hass: HomeAssistant, s7_server) -> None:
    tag = "DB2.DBD4:REAL"
    entry = await _setup(hass, s7_server[1], [tag])
    with pytest.raises(ServiceValidationError, match="needs a BOOL tag"):
        await hass.services.async_call(
            DOMAIN, "pulse_tag", {"entry_id": entry.entry_id, "tag": tag, "duration": 0.05}, blocking=True
        )
    await hass.config_entries.async_unload(entry.entry_id)
