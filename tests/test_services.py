"""Tests for the s7.write_tag and s7.pulse_tag services."""

from __future__ import annotations

import asyncio

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.s7.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_RACK,
    CONF_SLOT,
    CONF_TAGS,
    DOMAIN,
)


@pytest.fixture
async def loaded_entry(hass: HomeAssistant, s7_server):
    """Set up an s7 config entry with a writable DB2 BOOL tag."""
    _srv, port, _ = s7_server
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_RACK: 0,
            CONF_SLOT: 0,
            CONF_PORT: port,
            CONF_TAGS: ["DB2.DBX0.0:BOOL", "DB2.DBD4:REAL"],
        },
        unique_id=f"127.0.0.1:{port}:services",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    try:
        yield entry
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_write_tag_service(hass: HomeAssistant, loaded_entry) -> None:
    """write_tag service writes the value and a subsequent refresh sees it."""
    await hass.services.async_call(
        DOMAIN,
        "write_tag",
        {"entry_id": loaded_entry.entry_id, "tag": "DB2.DBD4:REAL", "value": "3.14"},
        blocking=True,
    )
    await hass.async_block_till_done()

    coordinator = loaded_entry.runtime_data
    assert abs(coordinator.data["DB2.DBD4:REAL"] - 3.14) < 0.001


async def test_write_tag_service_unknown_entry(hass: HomeAssistant, loaded_entry) -> None:
    """write_tag on a non-existent entry raises HomeAssistantError."""
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "write_tag",
            {"entry_id": "nope", "tag": "DB2.DBX0.0:BOOL", "value": "true"},
            blocking=True,
        )


async def test_pulse_tag_service_toggles_bit(hass: HomeAssistant, loaded_entry) -> None:
    """pulse_tag holds the bit True for duration seconds, then writes False."""
    coordinator = loaded_entry.runtime_data

    # Kick off the pulse and watch the bit flip during the hold.
    task = asyncio.create_task(
        hass.services.async_call(
            DOMAIN,
            "pulse_tag",
            {"entry_id": loaded_entry.entry_id, "tag": "DB2.DBX0.0:BOOL", "duration": 0.2},
            blocking=True,
        )
    )

    # Mid-pulse: bit should be True.
    await asyncio.sleep(0.1)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.data["DB2.DBX0.0:BOOL"] is True

    await task
    await hass.async_block_till_done()

    # After the pulse: bit should be False.
    await coordinator.async_refresh()
    assert coordinator.data["DB2.DBX0.0:BOOL"] is False


async def test_services_exist_without_an_entry(hass: HomeAssistant) -> None:
    """The services are registered by the integration, not by a config entry."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert hass.services.has_service(DOMAIN, "write_tag")
    assert hass.services.has_service(DOMAIN, "pulse_tag")


async def test_services_stay_after_the_last_unload(hass: HomeAssistant, loaded_entry) -> None:
    """Unloading the only entry keeps the services; calling one names the problem."""
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, "write_tag")
    assert hass.services.has_service(DOMAIN, "pulse_tag")
    with pytest.raises(HomeAssistantError, match="not loaded"):
        await hass.services.async_call(
            DOMAIN,
            "write_tag",
            {"entry_id": loaded_entry.entry_id, "tag": "DB2.DBX0.0:BOOL", "value": "true"},
            blocking=True,
        )


async def test_service_refuses_an_entry_of_another_integration(hass: HomeAssistant, loaded_entry) -> None:
    other = MockConfigEntry(domain="other")
    other.add_to_hass(hass)
    with pytest.raises(ServiceValidationError, match="No s7 config entry"):
        await hass.services.async_call(DOMAIN, "pulse_tag", {"entry_id": other.entry_id, "tag": "DB2.DBX0.0:BOOL"}, blocking=True)
