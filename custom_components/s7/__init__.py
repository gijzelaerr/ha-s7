"""The Siemens S7 PLC integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_RACK,
    CONF_SCAN_INTERVAL,
    CONF_SLOT,
    CONF_TAGS,
    CONF_USE_TLS,
    DEFAULT_PORT,
    DEFAULT_PROTOCOL,
    DEFAULT_RACK,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLOT,
    DOMAIN,
    PLATFORMS,
    plc_id,
)
from .coordinator import S7Coordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

type S7ConfigEntry = ConfigEntry[S7Coordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services, which exist whether or not a PLC is set up."""
    async_setup_services(hass)
    return True


@callback
def async_move_plc_id(hass: HomeAssistant, entry: ConfigEntry, old_id: str, new_id: str) -> None:
    """Rename the unique IDs and the device of a PLC, so its entities survive a new id."""
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.unique_id.startswith(f"{old_id}_"):
            new_unique_id = f"{new_id}_{entity.unique_id.removeprefix(f'{old_id}_')}"
            registry.async_update_entity(entity.entity_id, new_unique_id=new_unique_id)
    devices = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(devices, entry.entry_id):
        if (DOMAIN, old_id) in device.identifiers:
            devices.async_update_device(device.id, new_identifiers={(DOMAIN, new_id)})


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Move unique IDs and the device from the host name to the full PLC id."""
    if entry.version > 1:
        return False
    if entry.minor_version < 2:
        new_id = plc_id(entry.data)
        async_move_plc_id(hass, entry, entry.data[CONF_HOST], new_id)
        hass.config_entries.async_update_entry(entry, unique_id=new_id, minor_version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: S7ConfigEntry) -> bool:
    """Set up s7 from a config entry."""
    data = entry.data
    options = entry.options

    scan_seconds = options.get(CONF_SCAN_INTERVAL) or 0
    if scan_seconds <= 0:  # entries saved before the options form required a positive value
        scan_seconds = DEFAULT_SCAN_INTERVAL.total_seconds()
    scan_interval = timedelta(seconds=int(scan_seconds))

    coordinator = S7Coordinator(
        hass,
        host=data[CONF_HOST],
        rack=data.get(CONF_RACK, DEFAULT_RACK),
        slot=data.get(CONF_SLOT, DEFAULT_SLOT),
        port=data.get(CONF_PORT, DEFAULT_PORT),
        password=data.get(CONF_PASSWORD),
        use_tls=data.get(CONF_USE_TLS, False),
        tags=options.get(CONF_TAGS, data.get(CONF_TAGS, [])),
        scan_interval=scan_interval,
        protocol=data.get(CONF_PROTOCOL, DEFAULT_PROTOCOL),
    )

    try:
        await coordinator.async_connect()
    except Exception as err:
        raise ConfigEntryNotReady(f"Cannot connect to PLC at {coordinator.host}: {err}") from err
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    _async_remove_stale_entities(hass, entry, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


def _async_remove_stale_entities(hass: HomeAssistant, entry: S7ConfigEntry, coordinator: S7Coordinator) -> None:
    """Drop registry entries for tags that were removed from the configuration."""
    registry = er.async_get(hass)
    keep = {f"{coordinator.plc_id}_{tag}" for tag in coordinator.tags}
    diagnostic_prefix = f"{coordinator.plc_id}_diag_"
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.unique_id not in keep and not entity.unique_id.startswith(diagnostic_prefix):
            registry.async_remove(entity.entity_id)


async def async_unload_entry(hass: HomeAssistant, entry: S7ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_disconnect()
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: S7ConfigEntry) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
