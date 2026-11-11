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

_WRITE_TAG_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): cv.string,
        vol.Required("tag"): cv.string,
        vol.Required("value"): vol.Any(cv.string, vol.Coerce(float), cv.boolean),
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


def _coerce_value(raw: Any, datatype: str) -> Any:
    """Service ``value`` comes as a string from the UI — coerce to the obvious type.

    Text tags keep the string as it is, so ``"123"`` and ``"on"`` can be written
    to them. Users who need to force a type should use a template that yields
    the correct Python object directly.
    """
    if not isinstance(raw, str) or datatype.upper().startswith(_TEXT_TYPES):
        return raw
    lowered = raw.strip().lower()
    if lowered in ("true", "on", "yes"):
        return True
    if lowered in ("false", "off", "no"):
        return False
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


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
