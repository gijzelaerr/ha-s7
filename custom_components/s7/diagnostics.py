"""Diagnostics download for an s7 config entry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_PASSWORD

if TYPE_CHECKING:
    from . import S7ConfigEntry

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: S7ConfigEntry) -> dict[str, Any]:
    """Return the entry configuration, the tags and the coordinator's counters."""
    coordinator = entry.runtime_data
    connected_since = coordinator.connected_since
    update_interval = coordinator.update_interval
    return {
        "entry": {
            "title": entry.title,
            "unique_id": entry.unique_id,
            "version": f"{entry.version}.{entry.minor_version}",
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "tags": [
            {
                "address": address,
                "datatype": tag.datatype,
                "area": getattr(tag.area, "name", str(tag.area)),
                "size": tag.size,
                "has_value": address in (coordinator.data or {}),
            }
            for address, tag in coordinator.parsed_tags.items()
        ],
        "coordinator": {
            "plc_id": coordinator.plc_id,
            "update_interval_seconds": update_interval.total_seconds() if update_interval else None,
            "last_update_success": coordinator.last_update_success,
            "last_exception": repr(coordinator.last_exception) if coordinator.last_exception else None,
            "read_count": coordinator.read_count,
            "write_count": coordinator.write_count,
            "last_read_latency_seconds": coordinator.last_read_latency,
            "connected_since": connected_since.isoformat() if connected_since else None,
        },
    }
