"""A pulse must not leave its bit set."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from snap7.client import Client

from custom_components.s7 import coordinator as coordinator_module
from custom_components.s7.const import CONF_HOST, CONF_PORT, CONF_RACK, CONF_SLOT, CONF_TAGS, DOMAIN

BIT = "DB2.DBX0.0:BOOL"


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


def _bit_on_the_plc(port: int) -> bool:
    client = Client()
    client.connect("127.0.0.1", 0, 0, port)
    try:
        return bool(client.db_read(2, 0, 1)[0] & 1)
    finally:
        client.disconnect()


def _fail_releases(coordinator: Any, failures: int) -> None:
    write = coordinator._client.write_tag
    left = [failures]

    def write_tag(tag: Any, value: Any) -> None:
        if value is False and left[0] > 0:
            left[0] -= 1
            raise OSError("connection lost")
        write(tag, value)

    coordinator._client.write_tag = write_tag


async def test_cancelled_pulse_releases(hass: HomeAssistant, s7_server) -> None:
    port = s7_server[1]
    entry = await _setup(hass, port, [BIT])
    task = asyncio.create_task(entry.runtime_data.async_pulse_tag(BIT, 30))
    await asyncio.sleep(0.2)
    assert await hass.async_add_executor_job(_bit_on_the_plc, port)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await hass.async_block_till_done()
    assert not await hass.async_add_executor_job(_bit_on_the_plc, port)
    await hass.config_entries.async_unload(entry.entry_id)


async def test_release_retries_after_a_failure(hass: HomeAssistant, s7_server, monkeypatch) -> None:
    monkeypatch.setattr(coordinator_module, "_RECONNECT_BACKOFF_SECONDS", (0.0,))
    port = s7_server[1]
    entry = await _setup(hass, port, [BIT])
    coordinator = entry.runtime_data
    _fail_releases(coordinator, 1)
    await coordinator.async_pulse_tag(BIT, 0.01)
    assert not await hass.async_add_executor_job(_bit_on_the_plc, port)
    await hass.config_entries.async_unload(entry.entry_id)


async def test_release_gives_up_loudly(hass: HomeAssistant, s7_server, monkeypatch, caplog) -> None:
    monkeypatch.setattr(coordinator_module, "_RECONNECT_BACKOFF_SECONDS", (0.0,))
    entry = await _setup(hass, s7_server[1], [BIT])
    coordinator = entry.runtime_data
    _fail_releases(coordinator, 3)
    with pytest.raises((OSError, HomeAssistantError)):
        await coordinator.async_pulse_tag(BIT, 0.01)
    assert "may still be set" in caplog.text
    await hass.config_entries.async_unload(entry.entry_id)


async def test_unload_during_a_pulse_releases_and_disconnects(hass: HomeAssistant, s7_server) -> None:
    port = s7_server[1]
    entry = await _setup(hass, port, [BIT])
    coordinator = entry.runtime_data
    task = asyncio.create_task(coordinator.async_pulse_tag(BIT, 0.3))
    await asyncio.sleep(0.1)
    await hass.config_entries.async_unload(entry.entry_id)
    await task
    await hass.async_block_till_done()
    assert not coordinator._client.connected
    assert not await hass.async_add_executor_job(_bit_on_the_plc, port)
