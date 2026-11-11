"""Each PLC keeps its own entities and device, even on a shared host."""

from __future__ import annotations

import random
import time
from ctypes import c_char

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from snap7.server import Server as LegacyServer
from snap7.type import SrvArea

from custom_components.s7.const import CONF_HOST, CONF_PORT, CONF_PROTOCOL, CONF_RACK, CONF_SLOT, CONF_TAGS, DOMAIN, plc_id


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


TAG = "DB1.DBD0:REAL"


def test_plc_id() -> None:
    assert plc_id({CONF_HOST: "h", CONF_PORT: 102, CONF_RACK: 0, CONF_SLOT: 2}) == "h:102:0:2"
    assert plc_id({CONF_HOST: "h", CONF_PORT: 102, CONF_PROTOCOL: "s7commplus", CONF_SLOT: 2}) == "h:102"


async def test_two_ports_on_one_host_keep_their_entities(hass: HomeAssistant, s7_server) -> None:
    other, port = _start_server(bytearray(100))
    first = await _setup(hass, s7_server[1], [TAG])
    second = await _setup(hass, port, [TAG])
    registry = er.async_get(hass)
    for entry in (first, second):
        assert len(er.async_entries_for_config_entry(registry, entry.entry_id)) == 7  # sensor, number, four metrics, CPU state
        assert len(dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)) == 1
    await hass.config_entries.async_unload(first.entry_id)
    await hass.config_entries.async_unload(second.entry_id)
    other.stop()
    other.destroy()


async def test_two_slots_can_both_be_added(hass: HomeAssistant, s7_server) -> None:
    port = s7_server[1]
    for slot in (1, 2):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "127.0.0.1", CONF_PORT: port, CONF_RACK: 0, CONF_SLOT: slot, CONF_TAGS: TAG}
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
    for entry in hass.config_entries.async_entries(DOMAIN):
        await hass.config_entries.async_unload(entry.entry_id)


async def test_migration_keeps_entity_ids_and_history(hass: HomeAssistant, s7_server) -> None:
    port = s7_server[1]
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        data={CONF_HOST: "127.0.0.1", CONF_RACK: 0, CONF_SLOT: 0, CONF_PORT: port, CONF_TAGS: [TAG]},
        unique_id=f"127.0.0.1:{port}",
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    devices = dr.async_get(hass)
    old_device = devices.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, "127.0.0.1")})
    old = registry.async_get_or_create("sensor", DOMAIN, f"127.0.0.1_{TAG}", config_entry=entry, device_id=old_device.id)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    new_id = f"127.0.0.1:{port}:0:0"
    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert entry.unique_id == new_id
    migrated = registry.async_get(old.entity_id)
    assert migrated.unique_id == f"{new_id}_{TAG}"
    assert migrated.device_id == old_device.id
    assert devices.async_get_device_by_identifier((DOMAIN, new_id), entry.entry_id).id == old_device.id
    await hass.config_entries.async_unload(entry.entry_id)
