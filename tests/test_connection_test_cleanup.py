"""The config flow's throwaway connection must not outlive the test."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.core import HomeAssistant

from custom_components.s7 import config_flow
from custom_components.s7.const import CONF_HOST, CONF_PORT, CONF_PROTOCOL, CONF_RACK, CONF_SLOT, CONF_TAGS, DOMAIN


@pytest.mark.parametrize("protocol", ["legacy", "s7commplus"])
async def test_failed_read_closes_the_connection(
    hass: HomeAssistant, s7_server, s7commplus_server, monkeypatch, protocol: str
) -> None:
    port = s7_server[1] if protocol == "legacy" else s7commplus_server[1]
    clients: list[Any] = []
    create_client = config_flow.create_client

    def keep_client(*args: Any, **kwargs: Any) -> Any:
        clients.append(create_client(*args, **kwargs))
        return clients[-1]

    monkeypatch.setattr(config_flow, "create_client", keep_client)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: port,
            CONF_PROTOCOL: protocol,
            CONF_RACK: 0,
            CONF_SLOT: 0,
            CONF_TAGS: "DB99.DBD0:REAL",
        },
    )
    assert result["errors"] == {"base": "cannot_connect"}
    assert not clients[0].connected
