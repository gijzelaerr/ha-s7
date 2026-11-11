"""Service handlers for the s7 integration.

Exposes two global services, registered once when the integration is set up:

- ``s7.write_tag`` — write a value to any tag on a given PLC.
- ``s7.pulse_tag`` — write True, wait ``duration`` seconds, write False
  (momentary bit commands).

Both take an ``entry_id`` to identify which PLC to operate on, since a
single Home Assistant instance can have multiple S7 integrations
configured at once.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import probatio as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import S7Coordinator

if TYPE_CHECKING:
    from . import S7ConfigEntry

_LOGGER = logging.getLogger(__name__)

SERVICE_WRITE_TAG = "write_tag"
SERVICE_PULSE_TAG = "pulse_tag"

_TEXT_TYPES = ("STRING", "WSTRING", "FSTRING", "CHAR", "WCHAR")
_INTEGER_TYPES = frozenset({"BYTE", "SINT", "USINT", "INT", "UINT", "WORD", "DINT", "UDINT", "DWORD", "LINT", "ULINT", "LWORD"})
_FLOAT_TYPES = frozenset({"REAL", "LREAL"})
_TRUE_WORDS = frozenset({"true", "on", "yes", "1"})
_FALSE_WORDS = frozenset({"false", "off", "no", "0"})

_WRITE_TAG_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): cv.string,
        vol.Required("tag"): cv.string,
        vol.Required("value"): vol.Any(bool, int, float, str),
    }
)

_PULSE_TAG_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): cv.string,
        vol.Required("tag"): cv.string,
        vol.Optional("duration", default=0.5): vol.All(vol.Coerce(float), vol.Range(min=0.05, max=60.0)),
    }
)


def _get_coordinator(hass: HomeAssistant, entry_id: str) -> S7Coordinator:
    entry: S7ConfigEntry | None = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(f"No s7 config entry found for id {entry_id!r}")
    if entry.state is not ConfigEntryState.LOADED:
        raise HomeAssistantError(f"The s7 config entry {entry.title!r} is not loaded")
    return entry.runtime_data


def _coerce_value(raw: bool | int | float | str, datatype: str) -> Any:
    """Turn the service ``value`` into what the tag's datatype is written with.

    The value arrives as text from the UI and as a boolean, number or text
    from YAML and templates; the schema passes all of them through unchanged.

    - Text tags (``STRING``, ``WSTRING``, ``FSTRING``, ``CHAR``, ``WCHAR``) get
      the text, so ``"123"`` and ``"on"`` are written as typed.
    - ``BOOL`` takes a boolean, 0 or 1, or true/false, on/off, yes/no.
    - Integer tags take a whole number, also as text (``"42"``, ``"0x2A"``).
    - ``REAL`` and ``LREAL`` take any number, also as text (``"1e-05"``).
    - Every other type (``TIME``, ``DATE``, ...) gets the value as it came.

    A value that does not fit the datatype raises ``ServiceValidationError``.
    """
    base = datatype.upper()
    if base.startswith(_TEXT_TYPES):
        return raw if isinstance(raw, str) else str(raw)
    if base != "BOOL" and base not in _INTEGER_TYPES | _FLOAT_TYPES:
        return raw
    text = raw.strip() if isinstance(raw, str) else None
    if base == "BOOL":
        if isinstance(raw, bool):
            return raw
        if text is not None and text.lower() in _TRUE_WORDS | _FALSE_WORDS:
            return text.lower() in _TRUE_WORDS
        if text is None and raw in (0, 1):
            return bool(raw)
    elif base in _INTEGER_TYPES and not isinstance(raw, bool):
        if isinstance(raw, int):
            return raw
        if text is not None:
            for radix in (10, 0):  # 0 also reads 0x.., 0o.. and 0b..
                try:
                    return int(text, radix)
                except ValueError:
                    continue
        try:
            number = float(raw)
        except ValueError, OverflowError:
            number = float("nan")
        if number.is_integer():  # 3.0 and "3.0" are whole numbers too
            return int(number)
    elif base in _FLOAT_TYPES and not isinstance(raw, bool):
        try:
            return float(raw)
        except ValueError:
            pass
    raise ServiceValidationError(f"Cannot write {raw!r}: not a valid {base} value")


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the s7 service handlers. Called once, from ``async_setup``."""

    async def _write_tag(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, call.data["entry_id"])
        value = _coerce_value(call.data["value"], coordinator.resolve_tag(call.data["tag"]).datatype)
        await coordinator.async_write_tag(call.data["tag"], value)

    async def _pulse_tag(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, call.data["entry_id"])
        if coordinator.resolve_tag(call.data["tag"]).datatype.upper() != "BOOL":
            raise ServiceValidationError(f"pulse_tag needs a BOOL tag, got {call.data['tag']}")
        await coordinator.async_pulse_tag(call.data["tag"], call.data["duration"])

    hass.services.async_register(DOMAIN, SERVICE_WRITE_TAG, _write_tag, schema=_WRITE_TAG_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_PULSE_TAG, _pulse_tag, schema=_PULSE_TAG_SCHEMA)
