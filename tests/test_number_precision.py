"""Number entities keep integers exact and allow fractions on float tags."""

from __future__ import annotations

import random
import struct
import time
from ctypes import c_char

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from snap7.server import Server as LegacyServer
from snap7.type import SrvArea

from custom_components.s7.const import CONF_HOST, CONF_PORT, CONF_RACK, CONF_SLOT, CONF_TAGS, DOMAIN


def _start_server(data: bytearray) -> tuple[LegacyServer, int]:
    server = LegacyServer()
    server.register_area(SrvArea.DB, 1, (c_char * len(data)).from_buffer(data))
    port = random.randint(20000, 30000)
    server.start(tcp_port=port)
    time.sleep(0.2)
    return server, port


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


async def test_step_and_large_integer(hass: HomeAssistant) -> None:
    data = bytearray(100)
    struct.pack_into(">d", data, 0, 1.5)
    struct.pack_into(">q", data, 10, 2**53 + 1)
    struct.pack_into(">h", data, 20, 7)
    server, port = _start_server(data)
    lreal, lint, integer = "DB1.DBB0:LREAL", "DB1.DBB10:LINT", "DB1.DBW20:INT"
    entry = await _setup(hass, port, [lreal, lint, integer])
    registry = er.async_get(hass)

    def state(tag: str):
        unique_id = next(
            e.unique_id for e in er.async_entries_for_config_entry(registry, entry.entry_id) if e.unique_id.endswith(tag)
        )
        return hass.states.get(registry.async_get_entity_id("number", DOMAIN, unique_id))

    assert state(lreal).state == "1.5"
    assert state(lreal).attributes["step"] == 0.001
    assert state(lint).state == str(2**53 + 1)
    assert state(integer).state == "7"
    assert state(integer).attributes["step"] == 1
    await hass.config_entries.async_unload(entry.entry_id)
    server.stop()
    server.destroy()
