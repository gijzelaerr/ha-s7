"""Text platform — writable STRING/WSTRING/FSTRING tags in DB/M/Q areas."""

from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from snap7.type import Area

from .const import DOMAIN
from .coordinator import S7Coordinator
from .entity import S7BaseEntity

_STRING_TYPES = ("STRING", "WSTRING", "FSTRING")
_WRITABLE_AREAS = {Area.DB, Area.MK, Area.PA}


def _base_type(datatype: str) -> str:
    dt = datatype.upper()
    return dt.split("[", 1)[0] if "[" in dt else dt


def _string_capacity(datatype: str) -> int | None:
    """Extract the ``N`` from ``STRING[N]`` / ``WSTRING[N]`` / ``FSTRING[N]``."""
    dt = datatype.upper()
    if "[" in dt and dt.endswith("]"):
        try:
            return int(dt[dt.index("[") + 1 : -1])
        except ValueError:
            return None
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: S7Coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[S7Text] = []
    for raw, tag in coordinator.parsed_tags.items():
        if _base_type(tag.datatype) in _STRING_TYPES and tag.area in _WRITABLE_AREAS:
            entities.append(S7Text(coordinator, raw, tag.datatype))
    async_add_entities(entities)


class S7Text(S7BaseEntity, TextEntity):
    def __init__(self, coordinator: S7Coordinator, tag: str, datatype: str) -> None:
        super().__init__(coordinator, tag)
        capacity = _string_capacity(datatype)
        if capacity is not None:
            self._attr_native_max = capacity

    @property
    def native_value(self) -> str | None:
        value = self._value()
        return None if value is None else str(value)

    async def async_set_value(self, value: str) -> None:
        await self.coordinator.async_write_tag(self._tag, value)
