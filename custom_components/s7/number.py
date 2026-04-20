"""Number platform — writable numeric tags in DB/M/Q areas."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import S7Coordinator
from .entity import S7BaseEntity

# Writable numeric types that map to a number entity
_NUMBER_TYPES = {
    "BYTE", "SINT", "USINT",
    "INT", "UINT", "WORD",
    "DINT", "UDINT", "DWORD", "REAL",
    "LINT", "ULINT", "LWORD", "LREAL",
}

# Sensible min/max per S7 type
_RANGES: dict[str, tuple[float, float]] = {
    "BYTE": (0, 255),
    "USINT": (0, 255),
    "SINT": (-128, 127),
    "INT": (-32768, 32767),
    "UINT": (0, 65535),
    "WORD": (0, 65535),
    "DINT": (-2147483648, 2147483647),
    "UDINT": (0, 4294967295),
    "DWORD": (0, 4294967295),
    "REAL": (-3.4e38, 3.4e38),
    "LINT": (-(2**63), 2**63 - 1),
    "ULINT": (0, 2**64 - 1),
    "LWORD": (0, 2**64 - 1),
    "LREAL": (-1.7e308, 1.7e308),
}


def _tag_datatype(tag: str) -> str:
    if ":" not in tag:
        return ""
    dt = tag.rsplit(":", 1)[-1].upper()
    if "[" in dt:
        dt = dt.split("[", 1)[0]
    return dt


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: S7Coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[S7Number] = []
    for tag in coordinator.tags:
        dt = _tag_datatype(tag)
        upper = tag.upper().lstrip("%")
        if dt in _NUMBER_TYPES and (upper.startswith("DB") or upper.startswith("M") or upper.startswith("Q")):
            entities.append(S7Number(coordinator, tag, dt))
    async_add_entities(entities)


class S7Number(S7BaseEntity, NumberEntity):
    def __init__(self, coordinator: S7Coordinator, tag: str, datatype: str) -> None:
        super().__init__(coordinator, tag)
        lo, hi = _RANGES.get(datatype, (-1e18, 1e18))
        self._attr_native_min_value = lo
        self._attr_native_max_value = hi
        self._datatype = datatype

    @property
    def native_value(self) -> float | None:
        value = self._value()
        return float(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        # Integer types need int, REAL/LREAL accept float
        to_write: float | int = value if self._datatype in ("REAL", "LREAL") else int(value)
        await self.coordinator.async_write_tag(self._tag, to_write)
