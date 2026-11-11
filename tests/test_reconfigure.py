"""The reconfigure flow changes how a PLC is reached and keeps its entities."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.s7.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_RACK,
    CONF_SLOT,
    CONF_TAGS,
    CONF_USE_TLS,
    DOMAIN,
    plc_id,
)

TAGS = ["DB1.DBD0:REAL", "DB1.DBW4:INT", "DB1.DBX6.0:BOOL"]


def _entry(hass: HomeAssistant, port: int, **data) -> MockConfigEntry:
    data = {CONF_HOST: "127.0.0.1", CONF_RACK: 0, CONF_SLOT: 0, CONF_PORT: port, CONF_TAGS: TAGS} | data
    entry = MockConfigEntry(domain=DOMAIN, title="S7 127.0.0.1", data=data, unique_id=plc_id(data), minor_version=2)
    entry.add_to_hass(hass)
    return entry


async def _setup(hass: HomeAssistant, port: int, **data) -> MockConfigEntry:
    entry = _entry(hass, port, **data)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _suggested(result) -> dict:
    return {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }


def _entities(hass: HomeAssistant, entry: MockConfigEntry) -> dict[str, str]:
    """Entity ID -> unique ID of every entity of the entry."""
    registry = er.async_get(hass)
    return {e.entity_id: e.unique_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)}


async def test_form_shows_the_stored_connection(hass: HomeAssistant, s7_server) -> None:
    entry = await _setup(hass, s7_server[1])
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    suggested = _suggested(result)
    assert suggested[CONF_HOST] == "127.0.0.1"
    assert suggested[CONF_PORT] == s7_server[1]
    assert CONF_TAGS not in {str(key) for key in result["data_schema"].schema}
    await hass.config_entries.async_unload(entry.entry_id)


async def test_slot_change_keeps_entities_and_device(hass: HomeAssistant, s7_server) -> None:
    """The slot is part of the PLC id that unique IDs and the device are built from."""
    port = s7_server[1]
    entry = await _setup(hass, port)
    before = _entities(hass, entry)
    assert before
    assert all(unique_id.startswith(f"127.0.0.1:{port}:0:0_") for unique_id in before.values())
    devices = dr.async_get(hass)
    device_before = dr.async_entries_for_config_entry(devices, entry.entry_id)
    assert len(device_before) == 1

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "127.0.0.1", CONF_RACK: 0, CONF_SLOT: 2, CONF_PORT: port}
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert entry.data[CONF_SLOT] == 2
    assert entry.data[CONF_TAGS] == TAGS
    assert entry.unique_id == f"127.0.0.1:{port}:0:2"
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.plc_id == f"127.0.0.1:{port}:0:2"

    after = _entities(hass, entry)
    assert after.keys() == before.keys()
    for entity_id, unique_id in before.items():
        assert after[entity_id] == unique_id.replace(f"127.0.0.1:{port}:0:0_", f"127.0.0.1:{port}:0:2_")
    device_after = dr.async_entries_for_config_entry(devices, entry.entry_id)
    assert [d.id for d in device_after] == [d.id for d in device_before]
    assert device_after[0].identifiers == {(DOMAIN, f"127.0.0.1:{port}:0:2")}
    assert len(hass.states.async_all("switch")) == 1
    await hass.config_entries.async_unload(entry.entry_id)


async def test_protocol_change_keeps_entities(hass: HomeAssistant, s7_server, s7commplus_server) -> None:
    """Moving to S7CommPlus on another port drops rack and slot from the PLC id."""
    entry = await _setup(hass, s7_server[1])
    before = _entities(hass, entry)
    port = s7commplus_server[1]

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "127.0.0.1", CONF_PORT: port, CONF_PROTOCOL: "s7commplus", CONF_USE_TLS: False}
    )
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == f"127.0.0.1:{port}"
    assert entry.state is ConfigEntryState.LOADED
    after = _entities(hass, entry)
    assert after.keys() == before.keys()
    assert all(unique_id.startswith(f"127.0.0.1:{port}_") for unique_id in after.values())
    assert entry.runtime_data.data["DB1.DBW4:INT"] == 42
    await hass.config_entries.async_unload(entry.entry_id)


async def test_cannot_connect_saves_nothing(hass: HomeAssistant, s7_server) -> None:
    port = s7_server[1]
    entry = await _setup(hass, port)
    before = _entities(hass, entry)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "127.0.0.1", CONF_RACK: 0, CONF_SLOT: 0, CONF_PORT: 59999}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert _suggested(result)[CONF_PORT] == 59999
    assert entry.data[CONF_PORT] == port
    assert _entities(hass, entry) == before
    await hass.config_entries.async_unload(entry.entry_id)


async def test_tags_missing_on_the_new_plc_are_named(hass: HomeAssistant, s7_server) -> None:
    """The new address answers, but does not have a configured tag."""
    port = s7_server[1]
    entry = _entry(hass, 59999, **{CONF_TAGS: ["DB1.DBD0:REAL", "DB99.DBD0:REAL"]})
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "127.0.0.1", CONF_RACK: 0, CONF_SLOT: 0, CONF_PORT: port}
    )
    assert result["errors"] == {"base": "cannot_read_tag"}
    assert result["description_placeholders"] == {"tag": "DB99.DBD0:REAL"}
    assert entry.data[CONF_PORT] == 59999


async def test_address_of_another_entry_is_refused(hass: HomeAssistant, s7_server) -> None:
    port = s7_server[1]
    first = await _setup(hass, port)
    second = await _setup(hass, port, **{CONF_SLOT: 1})
    result = await second.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "127.0.0.1", CONF_RACK: 0, CONF_SLOT: 0, CONF_PORT: port}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert second.data[CONF_SLOT] == 1
    assert second.unique_id == f"127.0.0.1:{port}:0:1"
    for entry in (first, second):
        await hass.config_entries.async_unload(entry.entry_id)


async def test_entry_that_could_not_connect_loads_after_the_fix(hass: HomeAssistant, s7_server) -> None:
    """A wrong port leaves the entry retrying; correcting it sets the entry up at once."""
    port = s7_server[1]
    entry = _entry(hass, 59999)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "127.0.0.1", CONF_RACK: 0, CONF_SLOT: 0, CONF_PORT: port}
    )
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == f"127.0.0.1:{port}:0:0"
    assert len(_entities(hass, entry)) >= len(TAGS)
    await hass.config_entries.async_unload(entry.entry_id)


async def test_password_is_kept_changed_or_removed(hass: HomeAssistant, s7_server) -> None:
    """The stored password is offered in the masked field; emptying the field removes it."""
    port = s7_server[1]
    entry = await _setup(hass, port, **{CONF_PASSWORD: "old"})
    connection = {CONF_HOST: "127.0.0.1", CONF_RACK: 0, CONF_SLOT: 0, CONF_PORT: port}

    result = await entry.start_reconfigure_flow(hass)
    assert _suggested(result)[CONF_PASSWORD] == "old"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], connection | {CONF_PASSWORD: "new"})
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_PASSWORD] == "new"

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], connection)
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert CONF_PASSWORD not in entry.data
    assert entry.state is ConfigEntryState.LOADED
    await hass.config_entries.async_unload(entry.entry_id)
