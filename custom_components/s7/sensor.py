"""Sensor platform — user tags plus diagnostic metrics."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
    entities: list[SensorEntity] = []
    for raw, tag in coordinator.parsed_tags.items():
        if _base_type(tag.datatype) in _SENSOR_TYPES:
            entities.append(S7Sensor(coordinator, raw))

    # Diagnostic sensors (disabled by default; enable via Device settings).
    entities.extend(
        [
            S7DiagnosticSensor(
                coordinator,
                metric="read_count",
                name="Read count",
                state_class=SensorStateClass.TOTAL_INCREASING,
            ),
            S7DiagnosticSensor(
                coordinator,
                metric="write_count",
                name="Write count",
                state_class=SensorStateClass.TOTAL_INCREASING,
            ),
            S7DiagnosticSensor(
                coordinator,
                metric="last_read_latency",
                name="Last read latency",
                device_class=SensorDeviceClass.DURATION,
                native_unit_of_measurement=UnitOfTime.SECONDS,
                suggested_display_precision=3,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            S7DiagnosticSensor(
                coordinator,
                metric="connected_since",
                name="Connected since",
                device_class=SensorDeviceClass.TIMESTAMP,
            ),
        ]
    )
    async_add_entities(entities)


class S7Sensor(S7BaseEntity, SensorEntity):
    @property
    def native_value(self):
        return self._value()


class S7DiagnosticSensor(CoordinatorEntity[S7Coordinator], SensorEntity):
    """Sensor that reports a coordinator metric (read count, latency, etc.).

    Disabled by default — most users don't need to see them; operators can
    enable them from the device page when debugging.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: S7Coordinator,
        *,
        metric: str,
        name: str,
        **sensor_attrs: Any,
    ) -> None:
        super().__init__(coordinator)
        self._metric = metric
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.host}_diag_{metric}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.host)},
            name=f"S7 PLC {coordinator.host}",
            manufacturer="Siemens",
            model="S7",
        )
        for key, value in sensor_attrs.items():
            setattr(self, f"_attr_{key}", value)

    @property
    def native_value(self) -> Any:
        return getattr(self.coordinator, self._metric, None)
