"""A password the PLC refuses is reported as such, not as a failed connection.

The emulators have no password protection, so each test runs the real client
against the S7CommPlus emulator with its ``connect()`` replaced by one that
raises the library's ``S7AuthenticationError``, as a PLC refusing the password
makes it do.
"""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant.common import MockConfigEntry
from s7commplus import error as commplus_error
from snap7 import error as legacy_error

from custom_components.s7 import config_flow
from custom_components.s7.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_TAGS,
    CONF_USE_TLS,
    DOMAIN,
    plc_id,
)
from custom_components.s7.plc import is_authentication_error

AUTH_ERRORS = [commplus_error.S7AuthenticationError, legacy_error.S7AuthenticationError]


def _refuse_the_password(monkeypatch: pytest.MonkeyPatch, error: type[Exception]) -> None:
    """Make every client the config flow creates fail to connect with ``error``."""
    create_client = config_flow.create_client

    def refusing_client(*args: Any, **kwargs: Any) -> Any:
        client = create_client(*args, **kwargs)

        def connect() -> None:
            raise error("Legitimation failed, protection level unchanged at 3: the password was refused")

        client.connect = connect
        return client

    monkeypatch.setattr(config_flow, "create_client", refusing_client)


def _commplus_data(port: int, **data: Any) -> dict[str, Any]:
    return {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: port,
        CONF_PROTOCOL: "s7commplus",
        CONF_USE_TLS: False,
        CONF_PASSWORD: "known",
        CONF_TAGS: ["DB1.DBW4:INT"],
    } | data


async def _loaded_entry(hass: HomeAssistant, port: int) -> MockConfigEntry:
    data = _commplus_data(port)
    entry = MockConfigEntry(domain=DOMAIN, title="S7 127.0.0.1", data=data, unique_id=plc_id(data), minor_version=2)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.parametrize("error", AUTH_ERRORS)
def test_both_libraries_authentication_errors_are_recognised(error: type[Exception]) -> None:
    assert is_authentication_error(error("refused"))


@pytest.mark.parametrize("error", [commplus_error.S7ConnectionError, legacy_error.S7ConnectionError, OSError])
def test_other_connection_errors_are_not_authentication_errors(error: type[Exception]) -> None:
    assert not is_authentication_error(error("refused"))


@pytest.mark.parametrize("error", AUTH_ERRORS)
async def test_user_flow_reports_a_refused_password(
    hass: HomeAssistant, s7commplus_server, monkeypatch: pytest.MonkeyPatch, error: type[Exception]
) -> None:
    _refuse_the_password(monkeypatch, error)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    data = _commplus_data(s7commplus_server[1], **{CONF_TAGS: "DB1.DBW4:INT", CONF_PASSWORD: "wrong"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_reconfigure_reports_a_refused_password_and_saves_nothing(
    hass: HomeAssistant, s7commplus_server, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = await _loaded_entry(hass, s7commplus_server[1])
    _refuse_the_password(monkeypatch, commplus_error.S7AuthenticationError)
    result = await entry.start_reconfigure_flow(hass)
    connection = {key: value for key, value in _commplus_data(s7commplus_server[1]).items() if key != CONF_TAGS}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], connection | {CONF_PASSWORD: "wrong"})
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data[CONF_PASSWORD] == "known"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_options_flow_reports_a_refused_password_and_saves_nothing(
    hass: HomeAssistant, s7commplus_server, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = await _loaded_entry(hass, s7commplus_server[1])
    _refuse_the_password(monkeypatch, commplus_error.S7AuthenticationError)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 30, CONF_TAGS: "DB1.DBD0:REAL"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert CONF_TAGS not in entry.options
    await hass.config_entries.async_unload(entry.entry_id)
