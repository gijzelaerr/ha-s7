"""write_tag and pulse_tag look at the tag's type."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.s7.const import CONF_HOST, CONF_PORT, CONF_RACK, CONF_SLOT, CONF_TAGS, DOMAIN
from custom_components.s7.services import _coerce_value


async def _setup(hass: HomeAssistant, port: int, tags: list[str], **options) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1", CONF_RACK: 0, CONF_SLOT: 0, CONF_PORT: port, CONF_TAGS: tags},
        options=options,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.parametrize("value", ["on", "123", "1.5", "hello"])
async def test_string_tag_keeps_the_text(hass: HomeAssistant, s7_server, value: str) -> None:
    tag = "DB2.DBB0:STRING[20]"
    entry = await _setup(hass, s7_server[1], [tag])
    await hass.services.async_call(DOMAIN, "write_tag", {"entry_id": entry.entry_id, "tag": tag, "value": value}, blocking=True)
    await hass.async_block_till_done()
    assert entry.runtime_data.data[tag] == value
    await hass.config_entries.async_unload(entry.entry_id)


async def test_numeric_tag_still_converts(hass: HomeAssistant, s7_server) -> None:
    tag = "DB2.DBW40:INT"
    entry = await _setup(hass, s7_server[1], [tag])
    await hass.services.async_call(DOMAIN, "write_tag", {"entry_id": entry.entry_id, "tag": tag, "value": "123"}, blocking=True)
    await hass.async_block_till_done()
    assert entry.runtime_data.data[tag] == 123
    await hass.config_entries.async_unload(entry.entry_id)


async def test_pulse_refuses_a_non_bool_tag(hass: HomeAssistant, s7_server) -> None:
    tag = "DB2.DBD4:REAL"
    entry = await _setup(hass, s7_server[1], [tag])
    with pytest.raises(ServiceValidationError, match="needs a BOOL tag"):
        await hass.services.async_call(
            DOMAIN, "pulse_tag", {"entry_id": entry.entry_id, "tag": tag, "duration": 0.05}, blocking=True
        )
    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    ("datatype", "raw", "expected"),
    [
        ("REAL", "1e-05", 1e-05),
        ("REAL", 1e-05, 1e-05),
        ("REAL", "3", 3.0),
        ("LREAL", 7, 7.0),
        ("LREAL", " -2.5 ", -2.5),
        ("INT", "42", 42),
        ("INT", 42, 42),
        ("INT", "3.0", 3),
        ("INT", 3.0, 3),
        ("WORD", "0x2A", 42),
        ("LINT", "9007199254740993", 9007199254740993),
        ("BOOL", True, True),
        ("BOOL", "off", False),
        ("BOOL", "Yes", True),
        ("BOOL", 1, True),
        ("BOOL", "0", False),
        ("STRING[10]", 123, "123"),
        ("STRING[10]", "1e-05", "1e-05"),
        ("CHAR", "A", "A"),
        ("TIME", "0:0:0:1.5", "0:0:0:1.5"),
    ],
)
def test_coerce_value(datatype: str, raw, expected) -> None:
    result = _coerce_value(raw, datatype)
    assert result == expected
    assert type(result) is type(expected)


@pytest.mark.parametrize(
    ("datatype", "raw"),
    [
        ("INT", "1.5"),
        ("INT", 1.5),
        ("INT", "abc"),
        ("INT", True),
        ("DINT", "inf"),
        ("REAL", "abc"),
        ("REAL", False),
        ("BOOL", "maybe"),
        ("BOOL", 2),
        ("BOOL", 0.5),
    ],
)
def test_coerce_value_refuses_what_does_not_fit(datatype: str, raw) -> None:
    with pytest.raises(ServiceValidationError, match="not a valid"):
        _coerce_value(raw, datatype)


@pytest.mark.parametrize("value", [1e-05, "1e-05"])
async def test_small_float_is_written_as_a_number(hass: HomeAssistant, s7_server, value) -> None:
    """A float in exponent notation reached the PLC as text and failed."""
    tag = "DB2.DBD8:REAL"
    entry = await _setup(hass, s7_server[1], [tag])
    await hass.services.async_call(DOMAIN, "write_tag", {"entry_id": entry.entry_id, "tag": tag, "value": value}, blocking=True)
    await hass.async_block_till_done()
    assert entry.runtime_data.data[tag] == pytest.approx(1e-05)
    await hass.config_entries.async_unload(entry.entry_id)


async def test_native_bool_and_int_are_written(hass: HomeAssistant, s7_server) -> None:
    """YAML and templates send real booleans and numbers, not text."""
    bit, word = "DB2.DBX0.0:BOOL", "DB2.DBW40:INT"
    entry = await _setup(hass, s7_server[1], [bit, word])
    for tag, value in ((bit, True), (word, -7)):
        await hass.services.async_call(
            DOMAIN, "write_tag", {"entry_id": entry.entry_id, "tag": tag, "value": value}, blocking=True
        )
    await entry.runtime_data.async_refresh()  # the refresh after a write is debounced
    assert entry.runtime_data.data[bit] is True
    assert entry.runtime_data.data[word] == -7
    await hass.config_entries.async_unload(entry.entry_id)


async def test_value_that_does_not_fit_is_refused(hass: HomeAssistant, s7_server) -> None:
    tag = "DB2.DBW40:INT"
    entry = await _setup(hass, s7_server[1], [tag])
    with pytest.raises(ServiceValidationError, match="not a valid INT value"):
        await hass.services.async_call(
            DOMAIN, "write_tag", {"entry_id": entry.entry_id, "tag": tag, "value": "1.5"}, blocking=True
        )
    await hass.config_entries.async_unload(entry.entry_id)
