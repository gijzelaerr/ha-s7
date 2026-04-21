"""Tests for the diagnostic sensor metrics."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.s7.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_RACK,
    CONF_SLOT,
    CONF_TAGS,
    DOMAIN,
)

_EXPECTED_METRICS = ("read_count", "write_count", "last_read_latency", "connected_since")


async def test_diagnostic_sensors_registered(hass: HomeAssistant, s7_server) -> None:
    """All four diagnostic sensors appear in the entity registry, disabled by default."""
    _srv, port, _ = s7_server

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_RACK: 0,
            CONF_SLOT: 0,
            CONF_PORT: port,
            CONF_TAGS: ["DB1.DBD0:REAL"],
        },
        unique_id=f"127.0.0.1:{port}:diag",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    registry = er.async_get(hass)
    diag_entries = [
        re
        for re in registry.entities.values()
        if re.config_entry_id == entry.entry_id and re.unique_id.startswith("127.0.0.1_diag_")
    ]
    found_metrics = {re.unique_id.removeprefix("127.0.0.1_diag_") for re in diag_entries}
    assert found_metrics == set(_EXPECTED_METRICS)
    # Diagnostic-only sensors must not be enabled by default.
    assert all(re.disabled_by is not None for re in diag_entries)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_diagnostic_metrics_update_on_read_write(hass: HomeAssistant, s7_server) -> None:
    """read_count and write_count track coordinator activity; latency gets populated."""
    _srv, port, _ = s7_server

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_RACK: 0,
            CONF_SLOT: 0,
            CONF_PORT: port,
            CONF_TAGS: ["DB2.DBD0:REAL"],
        },
        unique_id=f"127.0.0.1:{port}:diag-counts",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    baseline_reads = coordinator.read_count

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.read_count == baseline_reads + 1
    assert coordinator.last_read_latency is not None
    assert coordinator.last_read_latency > 0
    assert coordinator.connected_since is not None

    await coordinator.async_write_tag("DB2.DBD0:REAL", 7.25)
    await hass.async_block_till_done()
    assert coordinator.write_count == 1

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
