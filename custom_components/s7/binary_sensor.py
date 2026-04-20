"""Binary sensor platform — BOOL tags (read-only)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import S7Coordinator
from .entity import S7BaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: S7Coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[S7BinarySensor] = []
    for tag in coordinator.tags:
        # Only BOOL tags from input or output areas (read-only).
        # Writable BOOLs in DB/M areas become switches instead (see switch.py).
        if tag.upper().endswith(":BOOL") and (tag.upper().startswith("I") or tag.upper().startswith("%I")):
            entities.append(S7BinarySensor(coordinator, tag))
    async_add_entities(entities)


class S7BinarySensor(S7BaseEntity, BinarySensorEntity):
    @property
    def is_on(self) -> bool | None:
        value = self._value()
        return bool(value) if value is not None else None
