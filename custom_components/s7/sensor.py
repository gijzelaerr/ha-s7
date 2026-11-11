"""Sensor platform — user tags plus diagnostic metrics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MAX_LENGTH_STATE_STATE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CHAR_TYPES, DOMAIN, NUMERIC_TYPES, STRING_TYPES, TIME_TYPES, base_type
from .coordinator import S7Coordinator
from .entity import S7BaseEntity

# Every type but BOOL gets a sensor.
_SENSOR_TYPES = NUMERIC_TYPES | STRING_TYPES | CHAR_TYPES | TIME_TYPES


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: S7Coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    for raw, tag in coordinator.parsed_tags.items():
        if base_type(tag.datatype) in _SENSOR_TYPES:
            entities.append(S7Sensor(coordinator, raw))

    # Diagnostic sensors (disabled by default; enable via Device settings).
    entities.extend(S7DiagnosticSensor(coordinator, description) for description in _DIAGNOSTIC_SENSORS)
    async_add_entities(entities)


class S7Sensor(S7BaseEntity, SensorEntity):
    @property
    def native_value(self):
        value = self._value()
        return value[:MAX_LENGTH_STATE_STATE] if isinstance(value, str) else value


@dataclass(frozen=True, kw_only=True)
class S7DiagnosticSensorDescription(SensorEntityDescription):
    """A coordinator metric and how to read it."""

    value_fn: Callable[[S7Coordinator], StateType | datetime]


# The key is part of the unique ID: do not rename.
_DIAGNOSTIC_SENSORS: tuple[S7DiagnosticSensorDescription, ...] = (
    S7DiagnosticSensorDescription(
        key="read_count",
        name="Read count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda coordinator: coordinator.read_count,
    ),
    S7DiagnosticSensorDescription(
        key="write_count",
        name="Write count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda coordinator: coordinator.write_count,
    ),
    S7DiagnosticSensorDescription(
        key="last_read_latency",
        name="Last read latency",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=3,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator: coordinator.last_read_latency,
    ),
    S7DiagnosticSensorDescription(
        key="connected_since",
        name="Connected since",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda coordinator: coordinator.connected_since,
    ),
)


class S7DiagnosticSensor(CoordinatorEntity[S7Coordinator], SensorEntity):
    """Sensor that reports a coordinator metric (read count, latency, etc.).

    Disabled by default — most users don't need to see them; operators can
    enable them from the device page when debugging.
    """

    entity_description: S7DiagnosticSensorDescription
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: S7Coordinator, description: S7DiagnosticSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.plc_id}_diag_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.plc_id)},
            name=f"S7 PLC {coordinator.host}",
            manufacturer="Siemens",
            model="S7",
        )

    @property
    def native_value(self) -> StateType | datetime:
        return self.entity_description.value_fn(self.coordinator)
