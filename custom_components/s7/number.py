"""Number platform — writable numeric tags in DB/M/Q areas."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import FLOAT_TYPES, NUMERIC_TYPES, WRITABLE_AREAS
from .coordinator import S7Coordinator
from .entity import S7BaseEntity

if TYPE_CHECKING:
    from . import S7ConfigEntry

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: S7ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[S7Number] = []
    for raw, tag in coordinator.parsed_tags.items():
        dt = tag.datatype.upper()
        if dt in NUMERIC_TYPES and tag.area in WRITABLE_AREAS:
            entities.append(S7Number(coordinator, raw, dt))
    async_add_entities(entities)


class S7Number(S7BaseEntity, NumberEntity):
    def __init__(self, coordinator: S7Coordinator, tag: str, datatype: str) -> None:
        super().__init__(coordinator, tag)
        lo, hi = _RANGES.get(datatype, (-1e18, 1e18))
        self._attr_native_min_value = lo
        self._attr_native_max_value = hi
        self._datatype = datatype
        if datatype in FLOAT_TYPES:
            self._attr_native_step = 0.001  # the default of 1 is for whole numbers

    @property
    def native_value(self) -> float | None:
        # Integers stay integers: LINT and ULINT do not fit a float exactly.
        return self._value()

    async def async_set_native_value(self, value: float) -> None:
        # Integer types need int, REAL/LREAL accept float
        to_write: float | int = value if self._datatype in FLOAT_TYPES else int(value)
        await self.coordinator.async_write_tag(self._tag, to_write)
