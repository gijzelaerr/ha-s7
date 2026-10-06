"""Tests for the S7CommPlus protocol backend, against the s7commplus emulator."""

from __future__ import annotations

from datetime import timedelta

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.s7.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_TAGS,
    DOMAIN,
    PROTOCOL_S7COMMPLUS,
)
from custom_components.s7.coordinator import S7Coordinator


def _coordinator(hass: HomeAssistant, port: int, tags: list[str]) -> S7Coordinator:
    return S7Coordinator(
        hass,
        host="127.0.0.1",
        rack=0,
        slot=1,
        port=port,
        password=None,
        use_tls=False,
        tags=tags,
        scan_interval=timedelta(seconds=60),
        protocol=PROTOCOL_S7COMMPLUS,
    )


async def test_commplus_reads_tags(hass: HomeAssistant, s7commplus_server) -> None:
    """Typed values are decoded from an S7CommPlus read."""
    _srv, port = s7commplus_server
    coordinator = _coordinator(hass, port, ["DB1.DBD0:REAL", "DB1.DBW4:INT", "DB1.DBX6.0:BOOL"])

    await coordinator.async_connect()
    await coordinator.async_refresh()

    assert coordinator.last_update_success
    data = coordinator.data or {}
    assert abs(data["DB1.DBD0:REAL"] - 23.5) < 0.01
    assert data["DB1.DBW4:INT"] == 42
    assert data["DB1.DBX6.0:BOOL"] is True

    await coordinator.async_disconnect()


async def test_commplus_write_tag(hass: HomeAssistant, s7commplus_server) -> None:
    """Writes land in the PLC, and a BOOL write keeps the neighbouring bits."""
    srv, port = s7commplus_server
    srv.get_db(2).data[0] = 0b0000_0100  # bit 2 already set

    coordinator = _coordinator(hass, port, ["DB2.DBD4:REAL", "DB2.DBX0.0:BOOL"])
    await coordinator.async_connect()

    await coordinator.async_write_tag("DB2.DBD4:REAL", 99.5)
    await coordinator.async_write_tag("DB2.DBX0.0:BOOL", True)
    await hass.async_block_till_done()
    await coordinator.async_refresh()

    data = coordinator.data or {}
    assert abs(data["DB2.DBD4:REAL"] - 99.5) < 0.01
    assert data["DB2.DBX0.0:BOOL"] is True
    assert srv.get_db(2).data[0] == 0b0000_0101

    await coordinator.async_shutdown()
    await coordinator.async_disconnect()


async def test_commplus_unreachable_plc_fails_update(hass: HomeAssistant) -> None:
    """A refused connection surfaces as a failed update rather than raising."""
    coordinator = _coordinator(hass, 1, ["DB1.DBD0:REAL"])
    await coordinator.async_refresh()
    assert not coordinator.last_update_success


async def test_config_flow_commplus(hass: HomeAssistant, s7commplus_server) -> None:
    """The user can pick the S7CommPlus protocol in the config flow."""
    _srv, port = s7commplus_server

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: port,
            CONF_PROTOCOL: PROTOCOL_S7COMMPLUS,
            CONF_TAGS: "DB1.DBD0:REAL",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_PROTOCOL] == PROTOCOL_S7COMMPLUS
