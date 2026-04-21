"""Service handlers for the s7 integration.

Exposes two global services:

- ``s7.write_tag`` — write a value to any tag on a given PLC.
- ``s7.pulse_tag`` — write True, wait ``duration`` seconds, write False
  (momentary bit commands).

Both take an ``entry_id`` to identify which PLC to operate on, since a
single Home Assistant instance can have multiple S7 integrations
configured at once.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import S7Coordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_WRITE_TAG = "write_tag"
SERVICE_PULSE_TAG = "pulse_tag"

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
    coordinators: dict[str, S7Coordinator] = hass.data.get(DOMAIN, {})
    coordinator = coordinators.get(entry_id)
    if coordinator is None:
        raise HomeAssistantError(f"No s7 config entry found for id {entry_id!r}")
    return coordinator


def _coerce_value(raw: Any) -> Any:
    """Service ``value`` comes as a string from the UI — coerce to the obvious type.

    Users who need to force a type should use a template that yields the
    correct Python object directly.
    """
    if not isinstance(raw, str):
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


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register the s7 service handlers. Safe to call multiple times."""
    if hass.services.has_service(DOMAIN, SERVICE_WRITE_TAG):
        return

    async def _write_tag(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, call.data["entry_id"])
        value = _coerce_value(call.data["value"])
        await coordinator.async_write_tag(call.data["tag"], value)

    async def _pulse_tag(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, call.data["entry_id"])
        await coordinator.async_pulse_tag(call.data["tag"], call.data["duration"])

    hass.services.async_register(DOMAIN, SERVICE_WRITE_TAG, _write_tag, schema=_WRITE_TAG_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_PULSE_TAG, _pulse_tag, schema=_PULSE_TAG_SCHEMA)


async def async_unload_services(hass: HomeAssistant) -> None:
    """Remove services when the last config entry unloads."""
    if not hass.data.get(DOMAIN):
        for name in (SERVICE_WRITE_TAG, SERVICE_PULSE_TAG):
            if hass.services.has_service(DOMAIN, name):
                hass.services.async_remove(DOMAIN, name)
