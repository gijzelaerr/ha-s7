"""Switch platform — writable BOOL tags in DB/M/Q areas."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from snap7.type import Area

from .const import DOMAIN
from .coordinator import S7Coordinator
from .entity import S7BaseEntity

_WRITABLE_BOOL_AREAS = {Area.DB, Area.MK, Area.PA}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: S7Coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[S7Switch] = []
    for raw, tag in coordinator.parsed_tags.items():
        if tag.datatype.upper() == "BOOL" and tag.area in _WRITABLE_BOOL_AREAS:
            entities.append(S7Switch(coordinator, raw))
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
