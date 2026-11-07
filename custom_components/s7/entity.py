"""Shared base entity for the s7 integration."""

from __future__ import annotations

import struct

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import S7Coordinator


def shortest_real(value: float) -> float:
    """Return the shortest decimal that is still the same 32-bit REAL.

    A REAL decoded to a Python float shows its binary noise: 23.1 becomes
    23.100000381469727.
    """
    exact = struct.pack(">f", value)
    for digits in range(6, 9):
        rounded = float(f"{value:.{digits}g}")
        try:
            if struct.pack(">f", rounded) == exact:
                return rounded
        except OverflowError:  # rounded up past the largest REAL
            continue
    return value


class S7BaseEntity(CoordinatorEntity[S7Coordinator]):
    """Base class — one PLC = one device; each tag = one entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: S7Coordinator, tag: str) -> None:
        super().__init__(coordinator)
        self._tag = tag
        self._attr_unique_id = f"{coordinator.host}_{tag}"
        self._attr_name = tag
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.host)},
            name=f"S7 PLC {coordinator.host}",
            manufacturer="Siemens",
            model="S7",
        )

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._tag in (self.coordinator.data or {})

    def _value(self):
        data = self.coordinator.data or {}
        value = data.get(self._tag)
        if isinstance(value, float) and self.coordinator.parsed_tags[self._tag].datatype.upper() == "REAL":
            return shortest_real(value)
        return value
