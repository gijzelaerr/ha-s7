"""Tests for the s7 config flow."""

from __future__ import annotations

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.selector import TextSelector
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.s7.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_RACK,
    CONF_SLOT,
    CONF_TAGS,
    DOMAIN,
)
from custom_components.s7.plc import LegacyPlcClient


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
    assert _suggested(options)[CONF_TAGS] == "DB1.DBD0:REAL\nDB1.DBW4:INT"
    await hass.config_entries.async_unload(result["result"].entry_id)


async def test_password_field_is_masked(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    selector = next(value for key, value in result["data_schema"].schema.items() if str(key) == CONF_PASSWORD)
    assert isinstance(selector, TextSelector)
    assert selector.config["type"] == "password"


@pytest.mark.parametrize("protocol", ["legacy", "s7commplus"])
async def test_user_flow_names_the_tag_that_cannot_be_read(
    hass: HomeAssistant, s7_server, s7commplus_server, protocol: str
) -> None:
    """The PLC answers, but one tag is in a data block it does not have."""
    port = s7_server[1] if protocol == "legacy" else s7commplus_server[1]
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
            CONF_RACK: 0,
            CONF_SLOT: 0,
            CONF_PORT: port,
            CONF_PROTOCOL: protocol,
            CONF_TAGS: "DB1.DBD0:REAL\nDB99.DBD0:REAL\nDB1.DBW4:INT",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_read_tag"}
    assert result["description_placeholders"] == {"tag": "DB99.DBD0:REAL"}


async def _loaded_entry(hass: HomeAssistant, port: int, tags: list[str]) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1", CONF_RACK: 0, CONF_SLOT: 0, CONF_PORT: port, CONF_TAGS: tags},
        unique_id=f"127.0.0.1:{port}:0:0",
        minor_version=2,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_options_flow_refuses_a_tag_that_cannot_be_read(hass: HomeAssistant, s7_server) -> None:
    """Configure reads the new tags before saving and names the one that fails."""
    entry = await _loaded_entry(hass, s7_server[1], ["DB1.DBD0:REAL"])
    result = await hass.config_entries.options.async_init(entry.entry_id)
    tags = "DB1.DBD0:REAL\nDB99.DBW0:INT"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"scan_interval": 30, CONF_TAGS: tags})
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_read_tag"}
    assert result["description_placeholders"] == {"tag": "DB99.DBW0:INT"}
    assert _suggested(result)[CONF_TAGS] == tags
    assert CONF_TAGS not in entry.options

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 30, CONF_TAGS: "DB1.DBD0:REAL\nDB1.DBW4:INT"}
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_TAGS] == ["DB1.DBD0:REAL", "DB1.DBW4:INT"]
    await hass.config_entries.async_unload(entry.entry_id)


async def test_options_flow_cannot_connect(hass: HomeAssistant, s7_server) -> None:
    """With the PLC gone the tags cannot be checked, so nothing is saved."""
    server, port, _db1 = s7_server
    entry = await _loaded_entry(hass, port, ["DB1.DBD0:REAL"])
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.async_unload(entry.entry_id)
    server.stop()
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 30, CONF_TAGS: "DB1.DBW4:INT"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert CONF_TAGS not in entry.options


async def test_options_flow_tags_can_be_cleared(hass: HomeAssistant, s7_server) -> None:
    """An emptied tag box arrives without the field; that removes every tag."""
    entry = await _loaded_entry(hass, s7_server[1], ["DB1.DBD0:REAL", "DB1.DBW4:INT"])
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"scan_interval": 30})
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_TAGS] == []
    assert entry.runtime_data.tags == []
    await hass.config_entries.async_unload(entry.entry_id)


async def test_connection_lost_during_the_test_read_is_not_blamed_on_tags(hass: HomeAssistant, s7_server) -> None:
    """The PLC goes away after the first failed read: that is a connection error."""
    server, port, _db1 = s7_server
    read_tags = LegacyPlcClient.read_tags

    def read_then_lose_the_plc(self: LegacyPlcClient, tags: list) -> list:
        try:
            return read_tags(self, tags)
        finally:
            self.disconnect()
            server.stop()

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(LegacyPlcClient, "read_tags", read_then_lose_the_plc)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "127.0.0.1", CONF_RACK: 0, CONF_SLOT: 0, CONF_PORT: port, CONF_TAGS: "DB1.DBD0:REAL\nDB99.DBD0:REAL"},
        )
    assert result["errors"] == {"base": "cannot_connect"}
