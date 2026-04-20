"""Tests for S7Coordinator polling the PLC."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant

from custom_components.s7.coordinator import S7Coordinator


async def test_coordinator_reads_tags(hass: HomeAssistant, s7_server) -> None:
    """Coordinator polls all configured tags and stores them by tag string."""
    _srv, port, _db1 = s7_server

    coordinator = S7Coordinator(
        hass,
        host="127.0.0.1",
        rack=0,
        slot=0,
        port=port,
        password=None,
        use_tls=False,
        tags=["DB1.DBD0:REAL", "DB1.DBW4:INT", "DB1.DBX6.0:BOOL"],
        scan_interval=timedelta(seconds=60),
    )

    await coordinator.async_connect()
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success
    data = coordinator.data or {}
    assert abs(data["DB1.DBD0:REAL"] - 23.5) < 0.01
    assert data["DB1.DBW4:INT"] == 42
    assert data["DB1.DBX6.0:BOOL"] is True

    await coordinator.async_disconnect()


async def test_coordinator_write_tag_updates_server(hass: HomeAssistant, s7_server) -> None:
    """Writing via the coordinator is visible to a subsequent read."""
    _srv, port, _ = s7_server

    coordinator = S7Coordinator(
        hass,
        host="127.0.0.1",
        rack=0,
        slot=0,
        port=port,
        password=None,
        use_tls=False,
        tags=["DB2.DBD0:REAL"],
        scan_interval=timedelta(seconds=60),
    )
    await coordinator.async_connect()

    await coordinator.async_write_tag("DB2.DBD0:REAL", 99.9)
    await hass.async_block_till_done()

    assert coordinator.data is not None
    assert abs(coordinator.data["DB2.DBD0:REAL"] - 99.9) < 0.01

    await coordinator.async_disconnect()


async def test_coordinator_update_failed_on_unreachable_host(hass: HomeAssistant) -> None:
    """Coordinator reports UpdateFailed when the PLC is unreachable."""
    coordinator = S7Coordinator(
        hass,
        host="127.0.0.1",
        rack=0,
        slot=0,
        port=59998,  # nothing listening
        password=None,
        use_tls=False,
        tags=["DB1.DBD0:REAL"],
        scan_interval=timedelta(seconds=60),
    )
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
