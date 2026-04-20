"""Shared base entity for the s7 integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import S7Coordinator


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
        return data.get(self._tag)
