"""Tests for S7Coordinator polling the PLC."""

from __future__ import annotations

from ctypes import c_char
from datetime import timedelta

from homeassistant.core import HomeAssistant
from snap7.type import SrvArea

from custom_components.s7.coordinator import S7Coordinator, parse_tags


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

    await coordinator.async_shutdown()
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


async def test_coordinator_reads_nodes7_syntax(hass: HomeAssistant, s7_server) -> None:
    """Coordinator accepts nodeS7-style tag addresses and polls them correctly."""
    _srv, port, _db1 = s7_server

    coordinator = S7Coordinator(
        hass,
        host="127.0.0.1",
        rack=0,
        slot=0,
        port=port,
        password=None,
        use_tls=False,
        tags=["DB1,R0", "DB1,I4", "DB1,X6.0"],
        scan_interval=timedelta(seconds=60),
    )

    await coordinator.async_connect()
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success
    data = coordinator.data or {}
    assert abs(data["DB1,R0"] - 23.5) < 0.01
    assert data["DB1,I4"] == 42
    assert data["DB1,X6.0"] is True

    await coordinator.async_disconnect()


async def test_coordinator_rejects_invalid_tags(hass: HomeAssistant) -> None:
    """Unparseable tag addresses raise at construction, not on first refresh."""
    import pytest

    with pytest.raises(ValueError, match="Invalid tag"):
        S7Coordinator(
            hass,
            host="127.0.0.1",
            rack=0,
            slot=0,
            port=1234,
            password=None,
            use_tls=False,
            tags=["not a tag"],
            scan_interval=timedelta(seconds=60),
        )


async def test_parsed_tags_exposes_dialect_subtypes(hass: HomeAssistant) -> None:
    """parsed_tags round-trips PLC4X and nodeS7 inputs to their source dialects."""
    from snap7.tags import NodeS7Tag, PLC4XTag

    coordinator = S7Coordinator(
        hass,
        host="127.0.0.1",
        rack=0,
        slot=0,
        port=1234,
        password=None,
        use_tls=False,
        tags=["DB1.DBD0:REAL", "DB1,R8"],
        scan_interval=timedelta(seconds=60),
    )
    parsed = coordinator.parsed_tags
    assert isinstance(parsed["DB1.DBD0:REAL"], PLC4XTag)
    assert isinstance(parsed["DB1,R8"], NodeS7Tag)


def test_parse_tags_rejects_arrays() -> None:
    """Array tags have no entity mapping, so they fail validation up front."""
    import pytest

    with pytest.raises(ValueError, match="array tags are not supported"):
        parse_tags(["DB1.DBD0:REAL[5]"])


async def test_coordinator_reads_more_than_twenty_tags(hass: HomeAssistant, s7_server) -> None:
    """A tag list longer than one python-snap7 request is read in full, in order."""
    server, port, db1 = s7_server
    for offset in range(10, 55):
        db1[offset] = offset
    # The server copies an area when it is registered, so register it again.
    server.register_area(SrvArea.DB, 1, (c_char * len(db1)).from_buffer(db1))

    tags = ["DB1.DBW4:INT", *(f"DB1.DBB{offset}:BYTE" for offset in range(10, 55)), "DB1.DBD0:REAL"]
    coordinator = S7Coordinator(
        hass,
        host="127.0.0.1",
        rack=0,
        slot=0,
        port=port,
        password=None,
        use_tls=False,
        tags=tags,
        scan_interval=timedelta(seconds=60),
    )

    await coordinator.async_connect()
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success
    data = coordinator.data or {}
    assert len(data) == 47
    assert data["DB1.DBW4:INT"] == 42
    for offset in range(10, 55):
        assert data[f"DB1.DBB{offset}:BYTE"] == offset
    assert abs(data["DB1.DBD0:REAL"] - 23.5) < 0.01

    await coordinator.async_disconnect()
