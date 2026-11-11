"""Sensors carry the state class, device class and unit their tag type implies."""

from __future__ import annotations

import random
import struct
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from snap7.server import Server as LegacyServer
from snap7.type import SrvArea

from custom_components.s7.const import CONF_HOST, CONF_PORT, CONF_RACK, CONF_SLOT, CONF_TAGS, DOMAIN
from custom_components.s7.sensor import duration_seconds, local_timestamp

_TAGS = {
    "time": "DB1:0:TIME",
    "negative_time": "DB1:4:TIME",
    "ltime": "DB1:8:LTIME",
    "s5time": "DB1:16:S5TIME",
    "whole_s5time": "DB1:18:S5TIME",
    "date": "DB1:20:DATE",
    "dt": "DB1:22:DT",
    "dtl": "DB1:30:DTL",
    "int": "DB1:42:INT",
    "real": "DB1:44:REAL",
    "string": "DB1:48:STRING[4]",
    "tod": "DB1:56:TOD",
    "byte": "DB1:60:BYTE",
}


def _db() -> bytearray:
    data = bytearray(64)
    struct.pack_into(">i", data, 0, 1500)  # TIME, milliseconds
    struct.pack_into(">i", data, 4, -1500)
    struct.pack_into(">q", data, 8, 2_500_000_000)  # LTIME, nanoseconds
    data[16:18] = bytes.fromhex("1234")  # S5TIME: base 100 ms, BCD 234
    data[18:20] = bytes.fromhex("2023")  # S5TIME: base 1 s, BCD 023
    struct.pack_into(">H", data, 20, (date(2026, 11, 11) - date(1990, 1, 1)).days)
    data[22:30] = bytes.fromhex("2611111230450004")  # DT, BCD 2026-11-11 12:30:45
    struct.pack_into(">HBBBBBBI", data, 30, 2026, 11, 11, 4, 12, 30, 45, 0)  # DTL
    struct.pack_into(">h", data, 42, 42)
    struct.pack_into(">f", data, 44, 23.5)
    data[48:52] = bytes([4, 2]) + b"hi"
    struct.pack_into(">I", data, 56, 3_723_000)  # TOD 01:02:03
    data[60] = 7
    return data


@pytest.fixture
async def states(hass: HomeAssistant) -> dict[str, State]:
    """Set up one sensor per type and return each sensor's state, keyed like _TAGS."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    server = LegacyServer()
    server.register_area(SrvArea.DB, 1, _db())
    port = random.randint(20000, 30000)
    server.start(tcp_port=port)
    time.sleep(0.2)
    try:
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "127.0.0.1", CONF_RACK: 0, CONF_SLOT: 0, CONF_PORT: port, CONF_TAGS: list(_TAGS.values())},
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        found: dict[str, State] = {}
        for key, tag in _TAGS.items():
            # The unique ID is the PLC id plus the tag string, as before.
            entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"127.0.0.1:{port}:0:0_{tag}")
            assert entity_id is not None, tag
            state = hass.states.get(entity_id)
            assert state is not None, tag
            found[key] = state
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        yield found
    finally:
        server.stop()
        server.destroy()


@pytest.mark.parametrize("key", ["int", "real", "byte"])
def test_numbers_are_measurements(states: dict[str, State], key: str) -> None:
    attrs = states[key].attributes
    assert attrs["state_class"] == "measurement"
    assert "device_class" not in attrs
    assert "unit_of_measurement" not in attrs


@pytest.mark.parametrize(
    ("key", "seconds"),
    [("time", 1.5), ("negative_time", -1.5), ("ltime", 2.5), ("s5time", 23.4), ("whole_s5time", 23.0)],
)
def test_times_are_durations_in_seconds(states: dict[str, State], key: str, seconds: float) -> None:
    state = states[key]
    assert float(state.state) == seconds
    assert state.attributes["device_class"] == "duration"
    assert state.attributes["unit_of_measurement"] == "s"
    assert state.attributes["state_class"] == "measurement"


def test_date_is_a_date(states: dict[str, State]) -> None:
    assert states["date"].state == "2026-11-11"
    assert states["date"].attributes["device_class"] == "date"
    assert "state_class" not in states["date"].attributes


@pytest.mark.parametrize("key", ["dt", "dtl"])
def test_date_and_time_is_a_timestamp(states: dict[str, State], key: str) -> None:
    """12:30:45 on the PLC is read as Amsterdam time; the state is in UTC."""
    assert states[key].state == "2026-11-11T11:30:45+00:00"
    assert states[key].attributes["device_class"] == "timestamp"
    assert "state_class" not in states[key].attributes


def test_other_types_stay_plain(states: dict[str, State]) -> None:
    assert states["string"].state == "hi"
    assert states["tod"].state == "1:02:03"
    for key in ("string", "tod"):
        assert "state_class" not in states[key].attributes
        assert "device_class" not in states[key].attributes


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0:0:0:1.500", 1.5),
        ("-0:0:0:1.500", -1.5),
        ("24:20:31:23.647", 2147483.647),
        ("-24:20:31:23.648", -2147483.648),
        ("0:00:23.400000", 23.4),
        ("0:00:23", 23.0),
        ("2:46:30", 9990.0),
        (timedelta(days=1, milliseconds=1), 86400.001),
        (timedelta(seconds=-2), -2.0),
        ("not a time", None),
        ("1:2", None),
        (None, None),
    ],
)
def test_duration_seconds(value: object, expected: float | None) -> None:
    assert duration_seconds(value) == expected


async def test_local_timestamp(hass: HomeAssistant) -> None:
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    amsterdam = ZoneInfo("Europe/Amsterdam")
    summer = datetime(2026, 7, 1, 12, 0, tzinfo=amsterdam)
    assert local_timestamp("2026-07-01T12:00:00.000000") == summer
    assert local_timestamp(datetime(2026, 7, 1, 12, 0)) == summer
    assert local_timestamp(summer) is summer
    assert local_timestamp("garbage") is None
    assert local_timestamp(None) is None
