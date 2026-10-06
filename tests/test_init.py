"""End-to-end setup/teardown test — spins up a config entry against the server fixture."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.s7.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_RACK,
    CONF_SLOT,
    CONF_TAGS,
    DOMAIN,
)


async def test_entry_setup_and_unload(hass: HomeAssistant, s7_server) -> None:
    """Config entry loads, entities register, unload cleanly."""
    _srv, port, _ = s7_server

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_RACK: 0,
            CONF_SLOT: 0,
            CONF_PORT: port,
            CONF_TAGS: ["DB1.DBD0:REAL", "DB1.DBW4:INT", "DB1.DBX6.0:BOOL"],
        },
        unique_id=f"127.0.0.1:{port}",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]

    # Sensor entities should have been created for REAL and INT tags
    states = [hass.states.get(s.entity_id) for s in hass.states.async_all("sensor")]
    sensor_values = {s.entity_id: s.state for s in states if s}
    assert len(sensor_values) == 2  # REAL + INT

    # Switch entity for the BOOL in DB area
    switches = hass.states.async_all("switch")
    assert len(switches) == 1

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_options_flow_edits_tags_and_removes_stale_entities(hass: HomeAssistant, s7_server) -> None:
    """Changing the tag list in the options flow reloads and drops entities of removed tags."""
    _srv, port, _ = s7_server

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_RACK: 0,
            CONF_SLOT: 0,
            CONF_PORT: port,
            CONF_TAGS: ["DB1.DBD0:REAL", "DB1.DBW4:INT"],
        },
        unique_id=f"127.0.0.1:{port}",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 2

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    bad = await hass.config_entries.options.async_configure(result["flow_id"], {"scan_interval": 30, CONF_TAGS: "not a tag"})
    assert bad["errors"] == {"base": "invalid_tags"}

    done = await hass.config_entries.options.async_configure(result["flow_id"], {"scan_interval": 30, CONF_TAGS: "DB1.DBD0:REAL"})
    await hass.async_block_till_done()
    assert done["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_TAGS] == ["DB1.DBD0:REAL"]
    assert len(hass.states.async_all("sensor")) == 1

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
