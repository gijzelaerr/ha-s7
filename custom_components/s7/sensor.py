"""Sensor platform — numeric and string tags."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import S7Coordinator
from .entity import S7BaseEntity

# Data types that map to a sensor entity (non-BOOL, readable numeric/string)
_SENSOR_TYPES = {
    "BYTE",
    "SINT",
    "USINT",
    "CHAR",
    "WCHAR",
    "INT",
    "UINT",
    "WORD",
    "DINT",
    "UDINT",
    "DWORD",
    "REAL",
    "LINT",
    "ULINT",
    "LWORD",
    "LREAL",
    "STRING",
    "WSTRING",
    "FSTRING",
    "TIME",
    "LTIME",
    "TOD",
    "LTOD",
    "DATE",
    "DT",
    "LDT",
    "DTL",
}


def _base_type(datatype: str) -> str:
    """Strip ``STRING[20]`` / ``REAL[5]`` down to base ``STRING`` / ``REAL``."""
    dt = datatype.upper()
    return dt.split("[", 1)[0] if "[" in dt else dt


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: S7Coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[S7Sensor] = []
    for raw, tag in coordinator.parsed_tags.items():
        if _base_type(tag.datatype) in _SENSOR_TYPES:
            entities.append(S7Sensor(coordinator, raw))
    async_add_entities(entities)


class S7Sensor(S7BaseEntity, SensorEntity):
    @property
    def native_value(self):
        return self._value()
