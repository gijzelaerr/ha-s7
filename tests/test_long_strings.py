"""Home Assistant states stop at 255 characters; WSTRING tags do not."""

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


async def test_long_value_is_clipped_in_both_entities(hass: HomeAssistant) -> None:
    data = bytearray(1000)
    struct.pack_into(">HH", data, 0, 400, 300)
    data[4:604] = ("x" * 300).encode("utf-16-be")
    server, port = _start_server(data)
    tag = "DB1.DBB0:WSTRING[400]"
    entry = await _setup(hass, port, [tag])
    registry = er.async_get(hass)
    for domain in ("sensor", "text"):
        entity_id = next(
            e.entity_id
            for e in er.async_entries_for_config_entry(registry, entry.entry_id)
            if e.domain == domain and "diag" not in e.unique_id
        )
        assert hass.states.get(entity_id).state == "x" * 255
    assert entry.runtime_data.data[tag] == "x" * 300
    await hass.config_entries.async_unload(entry.entry_id)
    server.stop()
    server.destroy()
