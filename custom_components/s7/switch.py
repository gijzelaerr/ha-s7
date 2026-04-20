"""Switch platform — writable BOOL tags in DB/M/Q areas."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    entities: list[S7Switch] = []
    for tag in coordinator.tags:
        upper = tag.upper().lstrip("%")
        if not upper.endswith(":BOOL"):
            continue
        # Writable areas: DB, M (Merker), Q (Output)
        if upper.startswith("DB") or upper.startswith("M") or upper.startswith("Q"):
            entities.append(S7Switch(coordinator, tag))
    async_add_entities(entities)


class S7Switch(S7BaseEntity, SwitchEntity):
    @property
    def is_on(self) -> bool | None:
        value = self._value()
        return bool(value) if value is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_write_tag(self._tag, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_write_tag(self._tag, False)
