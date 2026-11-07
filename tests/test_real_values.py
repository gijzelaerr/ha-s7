"""REAL states show the value, not its binary expansion."""

from __future__ import annotations

import math
import random
import struct
import time
from ctypes import c_char

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from snap7.server import Server as LegacyServer
from snap7.type import SrvArea

from custom_components.s7.const import CONF_HOST, CONF_PORT, CONF_RACK, CONF_SLOT, CONF_TAGS, DOMAIN
from custom_components.s7.entity import shortest_real


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


def _as_real(value: float) -> float:
    return struct.unpack(">f", struct.pack(">f", value))[0]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (23.1, 23.1),
        (0.1, 0.1),
        (-1.5, -1.5),
        (16777216.0, 16777216.0),
        (3.4028234663852886e38, 3.4028235e38),
        (math.inf, math.inf),
    ],
)
def test_shortest_real(value: float, expected: float) -> None:
    assert shortest_real(_as_real(value)) == expected
    assert _as_real(shortest_real(_as_real(value))) == _as_real(value)


def test_shortest_real_keeps_nan() -> None:
    assert math.isnan(shortest_real(math.nan))


async def test_states_show_the_short_form(hass: HomeAssistant) -> None:
    data = bytearray(100)
    struct.pack_into(">f", data, 0, 23.1)
    server, port = _start_server(data)
    tag = "DB1.DBD0:REAL"
    entry = await _setup(hass, port, [tag])
    registry = er.async_get(hass)
    for domain in ("sensor", "number"):
        entity_id = next(
            e.entity_id
            for e in er.async_entries_for_config_entry(registry, entry.entry_id)
            if e.domain == domain and "diag" not in e.unique_id
        )
        assert hass.states.get(entity_id).state == "23.1"
    await hass.config_entries.async_unload(entry.entry_id)
    server.stop()
    server.destroy()
