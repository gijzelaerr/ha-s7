"""Tests for the text platform — STRING/WSTRING tags."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.s7.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_RACK,
    CONF_SLOT,
    CONF_TAGS,
    DOMAIN,
)


async def test_string_in_db_becomes_text_entity(hass: HomeAssistant, s7_server) -> None:
    """A STRING tag in a writable DB area is exposed as a text entity."""
    _srv, port, _ = s7_server

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_RACK: 0,
            CONF_SLOT: 0,
            CONF_PORT: port,
            CONF_TAGS: ["DB2:10:STRING[20]"],
        },
        unique_id=f"127.0.0.1:{port}:text",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    text_entities = hass.states.async_all("text")
    assert len(text_entities) == 1

    # Round-trip: write, refresh, read back
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": text_entities[0].entity_id, "value": "hello"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(text_entities[0].entity_id)
    assert state is not None
    assert state.state == "hello"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_string_nodes7_syntax(hass: HomeAssistant, s7_server) -> None:
    """A nodeS7 STRING address (DB2,S10.20) maps to a text entity."""
    _srv, port, _ = s7_server

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_RACK: 0,
            CONF_SLOT: 0,
            CONF_PORT: port,
            CONF_TAGS: ["DB2,S10.20"],
        },
        unique_id=f"127.0.0.1:{port}:text-nodes7",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    text_entities = hass.states.async_all("text")
    assert len(text_entities) == 1

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
