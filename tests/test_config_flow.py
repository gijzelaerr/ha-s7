"""Tests for the s7 config flow."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.s7.const import (
    CONF_HOST,
    CONF_PASSWORD,
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


def _suggested(result) -> dict:
    """The suggested values a form was shown with, keyed by field name."""
    return {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }


def _tags_selector(result):
    return next(value for key, value in result["data_schema"].schema.items() if str(key) == CONF_TAGS)


async def test_user_flow_multiline_tags(hass: HomeAssistant, s7_server) -> None:
    """Tags pasted one per line create the entry (#61)."""
    _srv, port, _db1 = s7_server
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert _tags_selector(result).config["multiline"] is True

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "127.0.0.1", CONF_RACK: 0, CONF_SLOT: 0, CONF_PORT: port, CONF_TAGS: "DB1.DBD0:REAL\nDB1.DBW4:INT\n"},
    )
    await hass.async_block_till_done()
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_TAGS] == ["DB1.DBD0:REAL", "DB1.DBW4:INT"]


async def test_user_flow_keeps_input_after_cannot_connect(hass: HomeAssistant) -> None:
    """A failed connection test shows the form again with the input, but not the password (#61)."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    tags = "DB1.DBD0:REAL\nDB1.DBW4:INT"
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "127.0.0.1", CONF_RACK: 0, CONF_SLOT: 1, CONF_PORT: 59999, CONF_PASSWORD: "secret", CONF_TAGS: tags},
    )
    assert result2["errors"] == {"base": "cannot_connect"}
    suggested = _suggested(result2)
    assert suggested[CONF_TAGS] == tags
    assert suggested[CONF_HOST] == "127.0.0.1"
    assert suggested[CONF_PORT] == 59999
    assert suggested[CONF_SLOT] == 1
    assert CONF_PASSWORD not in suggested


async def test_user_flow_keeps_input_after_invalid_tags(hass: HomeAssistant) -> None:
    """A tag the parser refuses shows the form again with the tags to correct (#61)."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "127.0.0.1", CONF_PORT: 59999, CONF_TAGS: "DB1.DBD0:REAL\nnot a tag"},
    )
    assert result2["errors"] == {"base": "invalid_tags"}
    assert _suggested(result2)[CONF_TAGS] == "DB1.DBD0:REAL\nnot a tag"


async def test_options_flow_tags_field_is_multiline(hass: HomeAssistant, s7_server) -> None:
    """Configure shows the existing tags one per line in a multi-line box (#61)."""
    _srv, port, _db1 = s7_server
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "127.0.0.1", CONF_RACK: 0, CONF_SLOT: 0, CONF_PORT: port, CONF_TAGS: "DB1.DBD0:REAL;DB1.DBW4:INT"},
    )
    await hass.async_block_till_done()
    options = await hass.config_entries.options.async_init(result["result"].entry_id)
    assert _tags_selector(options).config["multiline"] is True
    default = next(key.default() for key in options["data_schema"].schema if str(key) == CONF_TAGS)
    assert default == "DB1.DBD0:REAL\nDB1.DBW4:INT"
    await hass.config_entries.async_unload(result["result"].entry_id)
