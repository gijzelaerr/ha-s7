"""Sensor platform — user tags plus diagnostic metrics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import MAX_LENGTH_STATE_STATE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CHAR_TYPES, CPU_STATE_RUN, CPU_STATE_STOP, DOMAIN, NUMERIC_TYPES, STRING_TYPES, TIME_TYPES, base_type
from .coordinator import S7Coordinator
from .entity import S7BaseEntity

if TYPE_CHECKING:
    from . import S7ConfigEntry

# Every type but BOOL gets a sensor.
_SENSOR_TYPES = NUMERIC_TYPES | STRING_TYPES | CHAR_TYPES | TIME_TYPES

_DURATION_TYPES = frozenset({"TIME", "LTIME", "S5TIME"})
_TIMESTAMP_TYPES = frozenset({"DT", "DTL"})


def duration_seconds(value: object) -> float | None:
    """Turn a decoded TIME, LTIME or S5TIME into seconds.

    python-snap7 gives LTIME as a timedelta, TIME as ``[-]d:h:m:s.mmm`` and
    S5TIME as ``h:mm:ss[.ffffff]``.
    """
    if isinstance(value, timedelta):
        return value.total_seconds()
    if not isinstance(value, str):
        return None
    negative = value.startswith("-")
    try:
        parts = [float(part) for part in value.lstrip("-").split(":")]
    except ValueError:
        return None
    if len(parts) == 4:
        days, hours, minutes, seconds = parts
    elif len(parts) == 3:
        days = 0.0
        hours, minutes, seconds = parts
    else:
        return None
    # Rounded to the microsecond, the finest step any of the three types has here.
    total = round(days * 86400 + hours * 3600 + minutes * 60 + seconds, 6)
    return -total if negative else total


def local_timestamp(value: object) -> datetime | None:
    """Turn a decoded DT or DTL into a datetime with a time zone.

    The PLC stores wall-clock time without a zone (python-snap7 gives DT as an
    ISO string and DTL as a naive datetime), and a timestamp sensor needs one,
    so the value is taken to be in Home Assistant's time zone.
    """
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt_util.get_default_time_zone())
    return value


async def async_setup_entry(
    hass: HomeAssistant,
    entry: S7ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for raw, tag in coordinator.parsed_tags.items():
        if base_type(tag.datatype) in _SENSOR_TYPES:
            entities.append(S7Sensor(coordinator, raw))

    # Diagnostic sensors (all but the CPU state are disabled by default; enable via Device settings).
    entities.extend(S7DiagnosticSensor(coordinator, description) for description in _DIAGNOSTIC_SENSORS)
    async_add_entities(entities)


class S7Sensor(S7BaseEntity, SensorEntity):
    """A tag as a sensor, with the device class and unit its type implies."""

    def __init__(self, coordinator: S7Coordinator, tag: str) -> None:
        super().__init__(coordinator, tag)
        self._datatype = base_type(coordinator.parsed_tags[tag].datatype)
        if self._datatype in NUMERIC_TYPES:
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._datatype in _DURATION_TYPES:
            self._attr_device_class = SensorDeviceClass.DURATION
            self._attr_native_unit_of_measurement = UnitOfTime.SECONDS
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._datatype == "DATE":
            self._attr_device_class = SensorDeviceClass.DATE
        elif self._datatype in _TIMESTAMP_TYPES:
            self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> StateType | date | datetime:
        value = self._value()
        if self._datatype in _DURATION_TYPES:
            return duration_seconds(value)
        if self._datatype in _TIMESTAMP_TYPES:
            return local_timestamp(value)
        return value[:MAX_LENGTH_STATE_STATE] if isinstance(value, str) else value


@dataclass(frozen=True, kw_only=True)
class S7DiagnosticSensorDescription(SensorEntityDescription):
    """A coordinator metric and how to read it."""

    value_fn: Callable[[S7Coordinator], StateType | datetime]


# The key is part of the unique ID: do not rename.
_DIAGNOSTIC_SENSORS: tuple[S7DiagnosticSensorDescription, ...] = (
    S7DiagnosticSensorDescription(
        key="read_count",
        entity_registry_enabled_default=False,
        name="Read count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda coordinator: coordinator.read_count,
    ),
    S7DiagnosticSensorDescription(
        key="write_count",
        entity_registry_enabled_default=False,
        name="Write count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda coordinator: coordinator.write_count,
    ),
    S7DiagnosticSensorDescription(
        key="last_read_latency",
        entity_registry_enabled_default=False,
        name="Last read latency",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=3,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator: coordinator.last_read_latency,
    ),
    S7DiagnosticSensorDescription(
        key="connected_since",
        entity_registry_enabled_default=False,
        name="Connected since",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda coordinator: coordinator.connected_since,
    ),
    S7DiagnosticSensorDescription(
        key="cpu_state",
        translation_key="cpu_state",
        device_class=SensorDeviceClass.ENUM,
        options=[CPU_STATE_RUN, CPU_STATE_STOP],
        value_fn=lambda coordinator: coordinator.cpu_state,
    ),
)


class S7DiagnosticSensor(CoordinatorEntity[S7Coordinator], SensorEntity):
    """Sensor that reports something about the PLC connection itself.

    The counters and timings are disabled by default — most users don't need
    to see them; operators can enable them from the device page when
    debugging. The CPU state is enabled.
    """

    entity_description: S7DiagnosticSensorDescription
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

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
