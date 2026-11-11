"""A lost connection is dropped at once, without holding up writes."""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from snap7.client import Client
from snap7.error import S7ConnectionError

from custom_components.s7.const import CONF_HOST, CONF_PORT, CONF_RACK, CONF_SLOT, CONF_TAGS, DOMAIN

WORD = "DB2.DBW0:INT"


async def _setup(hass: HomeAssistant, port: int, tags: list[str]) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1", CONF_RACK: 0, CONF_SLOT: 0, CONF_PORT: port, CONF_TAGS: tags},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _word_on_the_plc(port: int) -> int:
    client = Client()
    client.connect("127.0.0.1", 0, 0, port)
    try:
        return int.from_bytes(client.db_read(2, 0, 2), "big")
    finally:
        client.disconnect()


def _lose_connection_once(client: Any, method: str) -> threading.Event:
    """Make the next call of ``method`` fail as a lost connection; the event is set when it has."""
    real = getattr(client, method)
    lost = threading.Event()

    def call(*args: Any) -> Any:
        if not lost.is_set():
            lost.set()
            raise S7ConnectionError("Connection closed by peer")
        return real(*args)

    setattr(client, method, call)
    return lost


async def test_write_is_not_held_up_by_a_failed_read(hass: HomeAssistant, s7_server) -> None:
    port = s7_server[1]
    entry = await _setup(hass, port, [WORD])
    coordinator = entry.runtime_data
    connected_since = coordinator.connected_since
    lost = _lose_connection_once(coordinator._client, "read_each")

    refresh = hass.async_create_task(coordinator.async_refresh())
    while not lost.is_set():
        await asyncio.sleep(0.01)
    started = time.monotonic()
    await coordinator.async_write_tag(WORD, 1234)
    elapsed = time.monotonic() - started
    await refresh

    assert elapsed < 0.5
    assert await hass.async_add_executor_job(_word_on_the_plc, port) == 1234
    # The failed read closed the connection and the write opened a new one.
    assert coordinator.connected_since > connected_since

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_failed_write_drops_a_lost_connection(hass: HomeAssistant, s7_server) -> None:
    port = s7_server[1]
    entry = await _setup(hass, port, [WORD])
    coordinator = entry.runtime_data
    _lose_connection_once(coordinator._client, "write_tag")

    with pytest.raises(HomeAssistantError):
        await coordinator.async_write_tag(WORD, 1)
    assert not coordinator._client.connected

    await coordinator.async_write_tag(WORD, 2)
    assert coordinator._client.connected
    assert await hass.async_add_executor_job(_word_on_the_plc, port) == 2

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_refused_write_keeps_the_connection(hass: HomeAssistant, s7_server) -> None:
    entry = await _setup(hass, s7_server[1], [WORD])
    coordinator = entry.runtime_data
    connected_since = coordinator.connected_since

    with pytest.raises(HomeAssistantError):
        await coordinator.async_write_tag("DB99.DBW0:INT", 1)  # no such data block

    assert coordinator._client.connected
    assert coordinator.connected_since == connected_since

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
