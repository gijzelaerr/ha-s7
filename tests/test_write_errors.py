"""Failed writes reach the user as Home Assistant errors, not raw exceptions."""

from __future__ import annotations

import asyncio

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.s7.const import CONF_HOST, CONF_PORT, CONF_RACK, CONF_SLOT, CONF_TAGS, DOMAIN

BIT = "DB2.DBX0.0:BOOL"


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


async def test_invalid_address(hass: HomeAssistant, s7_server) -> None:
    entry = await _setup(hass, s7_server[1], [BIT])
    with pytest.raises(ServiceValidationError, match="Invalid tag address"):
        await hass.services.async_call(
            DOMAIN, "write_tag", {"entry_id": entry.entry_id, "tag": "nonsense", "value": "1"}, blocking=True
        )
    await hass.config_entries.async_unload(entry.entry_id)


async def test_value_of_the_wrong_type(hass: HomeAssistant, s7_server) -> None:
    entry = await _setup(hass, s7_server[1], ["DB2.DBW2:INT"])
    with pytest.raises(ServiceValidationError, match="Cannot write"):
        await hass.services.async_call(
            DOMAIN, "write_tag", {"entry_id": entry.entry_id, "tag": "DB2.DBW2:INT", "value": "abc"}, blocking=True
        )
    await hass.config_entries.async_unload(entry.entry_id)


async def test_unreachable_plc(hass: HomeAssistant, s7_server) -> None:
    server, port, _ = s7_server
    entry = await _setup(hass, port, [BIT])
    server.stop()
    await asyncio.sleep(0.1)
    entity_id = next(
        e.entity_id for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id) if e.domain == "switch"
    )
    with pytest.raises(HomeAssistantError, match="Failed to write"):
        await hass.services.async_call("switch", "turn_on", {"entity_id": entity_id}, blocking=True)
    await hass.config_entries.async_unload(entry.entry_id)
