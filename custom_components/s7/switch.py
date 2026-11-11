"""Switch platform — writable BOOL tags in DB/M/Q areas."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import WRITABLE_AREAS
from .entity import S7BaseEntity

if TYPE_CHECKING:
    from . import S7ConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: S7ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[S7Switch] = []
    for raw, tag in coordinator.parsed_tags.items():
        if tag.datatype.upper() == "BOOL" and tag.area in WRITABLE_AREAS:
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
