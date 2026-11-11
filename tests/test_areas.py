"""Inputs (I), flags (M) and outputs (Q): which entities they get, and that writes arrive."""

from __future__ import annotations

import random
import struct
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from snap7.server import Server as LegacyServer
from snap7.type import SrvArea

from custom_components.s7.const import CONF_HOST, CONF_PORT, CONF_RACK, CONF_SLOT, CONF_TAGS, DOMAIN

_TAGS = ["I0.0:BOOL", "I0.1:BOOL", "IW2:INT", "M10.5:BOOL", "MW20:INT", "Q0.0:BOOL", "QW2:INT"]


@dataclass
class Plc:
    entry: MockConfigEntry
    inputs: bytearray
    flags: bytearray
    outputs: bytearray
    entities: dict[tuple[str, str], str]  # (platform, tag) -> entity ID

    def entity_id(self, platform: str, tag: str) -> str:
        return self.entities[(platform, tag)]


@pytest.fixture
async def plc(hass: HomeAssistant) -> AsyncGenerator[Plc]:
    """A PLC with I, M and Q areas (the shared fixtures register DBs only)."""
    inputs, flags, outputs = bytearray(32), bytearray(32), bytearray(32)
    inputs[0] = 0b01  # I0.0 on, I0.1 off
    struct.pack_into(">h", inputs, 2, 1234)  # IW2
    server = LegacyServer()
    # The server serves the bytearray it is given, so these stay the PLC's memory.
    server.register_area(SrvArea.PE, 0, inputs)
    server.register_area(SrvArea.MK, 0, flags)
    server.register_area(SrvArea.PA, 0, outputs)
    port = random.randint(20000, 30000)
    server.start(tcp_port=port)
    time.sleep(0.2)
    try:
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "127.0.0.1", CONF_RACK: 0, CONF_SLOT: 0, CONF_PORT: port, CONF_TAGS: _TAGS},
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        prefix = f"127.0.0.1:{port}:0:0_"
        entities = {
            (e.domain, e.unique_id.removeprefix(prefix)): e.entity_id
            for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
            if "_diag_" not in e.unique_id
        }
        yield Plc(entry, inputs, flags, outputs, entities)
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        server.stop()
        server.destroy()


async def _refresh(hass: HomeAssistant, plc: Plc) -> None:
    await hass.data[DOMAIN][plc.entry.entry_id].async_refresh()
    await hass.async_block_till_done()


async def test_each_area_gets_the_right_entities(hass: HomeAssistant, plc: Plc) -> None:
    assert set(plc.entities) == {
        # Inputs are read-only: a binary sensor or a sensor, nothing writable.
        ("binary_sensor", "I0.0:BOOL"),
        ("binary_sensor", "I0.1:BOOL"),
        ("sensor", "IW2:INT"),
        # Flags and outputs can be written.
        ("switch", "M10.5:BOOL"),
        ("sensor", "MW20:INT"),
        ("number", "MW20:INT"),
        ("switch", "Q0.0:BOOL"),
        ("sensor", "QW2:INT"),
        ("number", "QW2:INT"),
    }


async def test_binary_sensor_follows_the_input(hass: HomeAssistant, plc: Plc) -> None:
    on, off = plc.entity_id("binary_sensor", "I0.0:BOOL"), plc.entity_id("binary_sensor", "I0.1:BOOL")
    assert hass.states.get(on).state == "on"
    assert hass.states.get(off).state == "off"

    plc.inputs[0] = 0b10
    await _refresh(hass, plc)
    assert hass.states.get(on).state == "off"
    assert hass.states.get(off).state == "on"


async def test_input_word_is_read(hass: HomeAssistant, plc: Plc) -> None:
    entity_id = plc.entity_id("sensor", "IW2:INT")
    assert hass.states.get(entity_id).state == "1234"

    struct.pack_into(">h", plc.inputs, 2, -5)
    await _refresh(hass, plc)
    assert hass.states.get(entity_id).state == "-5"


@pytest.mark.parametrize(
    ("tag", "area", "byte", "mask"), [("M10.5:BOOL", "flags", 10, 0b100000), ("Q0.0:BOOL", "outputs", 0, 0b1)]
)
async def test_switch_writes_the_bit(hass: HomeAssistant, plc: Plc, tag: str, area: str, byte: int, mask: int) -> None:
    memory: bytearray = getattr(plc, area)
    memory[byte] = 0b1000_0010  # other bits of the byte must survive
    entity_id = plc.entity_id("switch", tag)
    await _refresh(hass, plc)
    assert hass.states.get(entity_id).state == "off"

    await hass.services.async_call("switch", "turn_on", {"entity_id": entity_id}, blocking=True)
    await hass.async_block_till_done()
    assert memory[byte] == 0b1000_0010 | mask
    assert hass.states.get(entity_id).state == "on"

    await hass.services.async_call("switch", "turn_off", {"entity_id": entity_id}, blocking=True)
    await hass.async_block_till_done()
    assert memory[byte] == 0b1000_0010
    # The refresh after a second write within the cooldown is debounced, so ask for one.
    await _refresh(hass, plc)
    assert hass.states.get(entity_id).state == "off"


@pytest.mark.parametrize(("tag", "area", "offset"), [("MW20:INT", "flags", 20), ("QW2:INT", "outputs", 2)])
async def test_number_writes_the_word(hass: HomeAssistant, plc: Plc, tag: str, area: str, offset: int) -> None:
    memory: bytearray = getattr(plc, area)
    number, sensor = plc.entity_id("number", tag), plc.entity_id("sensor", tag)
    assert hass.states.get(number).state == "0"

    await hass.services.async_call("number", "set_value", {"entity_id": number, "value": -321}, blocking=True)
    await hass.async_block_till_done()
    assert struct.unpack_from(">h", memory, offset)[0] == -321
    assert hass.states.get(number).state == "-321"
    assert hass.states.get(sensor).state == "-321"
