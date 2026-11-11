"""One tag the PLC cannot read must not take the other entities down."""

from __future__ import annotations

import logging
from ctypes import c_char

import pytest
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from snap7.type import SrvArea

from custom_components.s7.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_RACK,
    CONF_SLOT,
    CONF_TAGS,
    DOMAIN,
    PROTOCOL_LEGACY,
    PROTOCOL_S7COMMPLUS,
)

REAL = "DB1.DBD0:REAL"
INT = "DB1.DBW4:INT"
BOOL = "DB1.DBX6.0:BOOL"
MISSING = "DB99.DBW0:INT"  # no such data block on either emulator


async def _setup(hass: HomeAssistant, port: int, tags: list[str], protocol: str) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_RACK: 0,
            CONF_SLOT: 0,
            CONF_PORT: port,
            CONF_PROTOCOL: protocol,
            CONF_TAGS: tags,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _states(hass: HomeAssistant, entry: MockConfigEntry, tag: str) -> dict[str, str]:
    """State of each entity that shows ``tag`` (a tag can have a sensor and a number), by domain."""
    registry = er.async_get(hass)
    states: dict[str, str] = {}
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.unique_id.endswith(f"_{tag}"):
            state = hass.states.get(entity.entity_id)
            assert state is not None
            states[entity.domain] = state.state
    assert states
    return states


def _unavailable(hass: HomeAssistant, entry: MockConfigEntry, tag: str) -> bool:
    return set(_states(hass, entry, tag).values()) == {STATE_UNAVAILABLE}


def _warnings(caplog: pytest.LogCaptureFixture, tag: str) -> int:
    return sum(1 for r in caplog.records if r.levelno == logging.WARNING and tag in r.getMessage())


@pytest.mark.parametrize("protocol", [PROTOCOL_LEGACY, PROTOCOL_S7COMMPLUS])
async def test_missing_db_leaves_the_other_tags_available(
    hass: HomeAssistant, request: pytest.FixtureRequest, caplog: pytest.LogCaptureFixture, protocol: str
) -> None:
    server = request.getfixturevalue("s7_server" if protocol == PROTOCOL_LEGACY else "s7commplus_server")
    entry = await _setup(hass, server[1], [REAL, MISSING, INT, BOOL], protocol)
    coordinator = hass.data[DOMAIN][entry.entry_id]

    assert coordinator.last_update_success
    assert float(_states(hass, entry, REAL)["sensor"]) == 23.5
    assert _states(hass, entry, INT)["sensor"] == "42"
    assert set(_states(hass, entry, BOOL).values()) == {"on"}
    assert _unavailable(hass, entry, MISSING)
    assert list(coordinator.failed_tags) == [MISSING]

    # The connection stays up and the bad tag is reported once, not every poll.
    connected_since = coordinator.connected_since
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.last_update_success
    assert coordinator.connected_since == connected_since
    assert _states(hass, entry, INT)["sensor"] == "42"
    assert _unavailable(hass, entry, MISSING)
    assert _warnings(caplog, MISSING) == 1

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_tag_comes_back_when_its_db_appears(hass: HomeAssistant, s7_server) -> None:
    server, port, _db1 = s7_server
    entry = await _setup(hass, port, [INT, MISSING], PROTOCOL_LEGACY)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert _unavailable(hass, entry, MISSING)

    db99 = bytearray(b"\x00\x07" + bytes(8))
    server.register_area(SrvArea.DB, 99, (c_char * len(db99)).from_buffer(db99))
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert _states(hass, entry, MISSING)["sensor"] == "7"
    assert coordinator.failed_tags == {}

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_poll_fails_when_no_tag_can_be_read(hass: HomeAssistant, s7_server) -> None:
    entry = await _setup(hass, s7_server[1], [INT], PROTOCOL_LEGACY)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator._parsed_tags[INT].db_number = 98  # the block is gone from the PLC

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
    assert _unavailable(hass, entry, INT)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
