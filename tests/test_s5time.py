"""S5TIME tags show as a sensor with the duration the PLC holds (#56)."""

from __future__ import annotations

import random
import time
from ctypes import c_char

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from snap7.server import Server as LegacyServer
from snap7.type import SrvArea

from custom_components.s7.const import CONF_HOST, CONF_PORT, CONF_RACK, CONF_SLOT, CONF_TAGS, DOMAIN


async def test_s5time_is_a_sensor(hass: HomeAssistant) -> None:
    data = bytearray(16)
    data[0:2] = bytes.fromhex("1234")  # time base 1 (100 ms), BCD 234 -> 23.4 s
    server = LegacyServer()
    server.register_area(SrvArea.DB, 1, (c_char * len(data)).from_buffer(data))
    port = random.randint(20000, 30000)
    server.start(tcp_port=port)
    time.sleep(0.2)
    try:
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "127.0.0.1", CONF_RACK: 0, CONF_SLOT: 0, CONF_PORT: port, CONF_TAGS: ["DB1.DBW0:S5TIME"]},
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        sensors = [
            e.entity_id
            for e in er.async_entries_for_config_entry(registry, entry.entry_id)
            if e.domain == "sensor" and "diag" not in e.unique_id
        ]
        assert len(sensors) == 1
        assert hass.states.get(sensors[0]).state == "0:00:23.400000"
        await hass.config_entries.async_unload(entry.entry_id)
    finally:
        server.stop()
        server.destroy()
