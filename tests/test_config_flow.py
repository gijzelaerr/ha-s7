"""Tests for the s7 config flow."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.s7.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_RACK,
    CONF_SLOT,
    CONF_TAGS,
    DOMAIN,
)


async def test_user_flow_success(hass: HomeAssistant, s7_server) -> None:
    """User provides valid PLC details and tags → entry is created."""
    _srv, port, _db1 = s7_server

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
            CONF_RACK: 0,
            CONF_SLOT: 0,
            CONF_PORT: port,
            CONF_TAGS: "DB1.DBD0:REAL; DB1.DBW4:INT",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_HOST] == "127.0.0.1"
    assert result2["data"][CONF_TAGS] == ["DB1.DBD0:REAL", "DB1.DBW4:INT"]


async def test_user_flow_nodes7_syntax(hass: HomeAssistant, s7_server) -> None:
    """User can configure nodeS7-style tags (commas stay inside addresses)."""
    _srv, port, _ = s7_server

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
            CONF_RACK: 0,
            CONF_SLOT: 0,
            CONF_PORT: port,
            CONF_TAGS: "DB1,R0; DB1,I4",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_TAGS] == ["DB1,R0", "DB1,I4"]


async def test_user_flow_invalid_tag_rejected(hass: HomeAssistant, s7_server) -> None:
    """Unparseable tag addresses surface as invalid_tags without touching the PLC."""
    _srv, port, _ = s7_server

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
            CONF_RACK: 0,
            CONF_SLOT: 0,
            CONF_PORT: port,
            CONF_TAGS: "this is not a tag",
        },
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_tags"}


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """No server listening → config flow reports cannot_connect."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})

    # Use an unused port so the connect attempt fails fast
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
            CONF_RACK: 0,
            CONF_SLOT: 0,
            CONF_PORT: 59999,  # nothing listening
            CONF_TAGS: "",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_flow_duplicate_aborts(hass: HomeAssistant, s7_server) -> None:
    """Adding the same host:port twice aborts the second attempt."""
    _srv, port, _ = s7_server

    # First flow
    first = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    await hass.config_entries.flow.async_configure(
        first["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
            CONF_RACK: 0,
            CONF_SLOT: 0,
            CONF_PORT: port,
            CONF_TAGS: "",
        },
    )
    await hass.async_block_till_done()

    # Second flow — same host/port
    second = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        second["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
            CONF_RACK: 0,
            CONF_SLOT: 0,
            CONF_PORT: port,
            CONF_TAGS: "",
        },
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
