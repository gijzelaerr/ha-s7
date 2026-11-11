"""The diagnostics download shows the configuration without the password."""

from __future__ import annotations

import json

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.s7.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_RACK, CONF_SLOT, CONF_TAGS, DOMAIN
from custom_components.s7.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics(hass: HomeAssistant, s7_server) -> None:
    port = s7_server[1]
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="S7 127.0.0.1",
        data={
            CONF_HOST: "127.0.0.1",
            CONF_RACK: 0,
            CONF_SLOT: 0,
            CONF_PORT: port,
            CONF_PASSWORD: "hunter2",
            CONF_TAGS: ["DB1.DBD0:REAL"],
        },
        options={"scan_interval": 15, CONF_TAGS: ["DB1.DBD0:REAL", "DB2.DBW40:INT"]},
        unique_id=f"127.0.0.1:{port}:0:0",
        minor_version=2,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        DOMAIN, "write_tag", {"entry_id": entry.entry_id, "tag": "DB2.DBW40:INT", "value": 5}, blocking=True
    )
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, entry)

    text = json.dumps(result)  # the download is JSON
    assert "hunter2" not in text
    assert result["entry"]["data"][CONF_PASSWORD] == "**REDACTED**"
    assert result["entry"]["data"][CONF_HOST] == "127.0.0.1"
    assert result["entry"]["data"][CONF_PORT] == port
    assert result["entry"]["options"]["scan_interval"] == 15
    assert result["entry"]["unique_id"] == f"127.0.0.1:{port}:0:0"

    assert result["tags"] == [
        {"address": "DB1.DBD0:REAL", "datatype": "REAL", "area": "DB", "size": 4, "has_value": True},
        {"address": "DB2.DBW40:INT", "datatype": "INT", "area": "DB", "size": 2, "has_value": True},
    ]

    counters = result["coordinator"]
    assert counters["plc_id"] == f"127.0.0.1:{port}:0:0"
    assert counters["update_interval_seconds"] == 15
    assert counters["last_update_success"] is True
    assert counters["last_exception"] is None
    assert counters["failed_tags"] == {}
    assert counters["read_count"] >= 1
    assert counters["write_count"] == 1
    assert counters["last_read_latency_seconds"] >= 0
    assert counters["connected_since"].endswith("+00:00")

    await hass.config_entries.async_unload(entry.entry_id)
