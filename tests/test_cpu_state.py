"""Tests for the CPU state sensor."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from s7commplus import CPUState as CommPlusCPUState

from custom_components.s7.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_RACK,
    CONF_SLOT,
    CONF_TAGS,
    DOMAIN,
    PROTOCOL_S7COMMPLUS,
)


async def _setup(hass: HomeAssistant, port: int, **extra: object) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_RACK: 0,
            CONF_SLOT: 0,
            CONF_PORT: port,
            CONF_TAGS: ["DB1.DBW4:INT"],
            **extra,
        },
        unique_id=f"127.0.0.1:{port}:cpu-state",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _state(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.runtime_data.plc_id}_diag_cpu_state")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["device_class"] == SensorDeviceClass.ENUM
    assert state.attributes["options"] == ["run", "stop"]
    return state.state


async def test_cpu_state_follows_the_plc_on_classic_s7(hass: HomeAssistant, s7_server) -> None:
    """The sensor shows Run, then Stop once the CPU stops, on the classic protocol."""
    server, port, _ = s7_server
    entry = await _setup(hass, port)
    assert _state(hass, entry) == "run"

    server.set_cpu_status(4)  # STOP
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert _state(hass, entry) == "stop"
    # A stopped CPU still answers reads, so the tags stay available.
    assert entry.runtime_data.data["DB1.DBW4:INT"] == 42

    server.set_cpu_status(0)  # the CPU reports neither Run nor Stop
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert _state(hass, entry) == STATE_UNKNOWN

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_cpu_state_follows_the_plc_on_s7commplus(hass: HomeAssistant, s7commplus_server) -> None:
    """The sensor shows Run, then Stop once the CPU stops, on S7CommPlus."""
    server, port = s7commplus_server
    entry = await _setup(hass, port, **{CONF_PROTOCOL: PROTOCOL_S7COMMPLUS})
    assert _state(hass, entry) == "run"

    server.cpu_state = CommPlusCPUState.STOP
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert _state(hass, entry) == "stop"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
