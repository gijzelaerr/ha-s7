"""The Siemens S7 PLC integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

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
)
from .coordinator import S7Coordinator
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up s7 from a config entry."""
    data = entry.data
    options = entry.options

    scan_seconds = options.get(CONF_SCAN_INTERVAL) or DEFAULT_SCAN_INTERVAL.total_seconds()
    scan_interval = timedelta(seconds=int(scan_seconds))

    coordinator = S7Coordinator(
        hass,
        host=data[CONF_HOST],
        rack=data.get(CONF_RACK, DEFAULT_RACK),
        slot=data.get(CONF_SLOT, DEFAULT_SLOT),
        port=data.get(CONF_PORT, DEFAULT_PORT),
        password=data.get(CONF_PASSWORD),
        use_tls=data.get(CONF_USE_TLS, False),
        tags=data.get(CONF_TAGS, []),
        scan_interval=scan_interval,
        protocol=data.get(CONF_PROTOCOL, DEFAULT_PROTOCOL),
    )

    await coordinator.async_connect()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_setup_services(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: S7Coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_disconnect()
        await async_unload_services(hass)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
