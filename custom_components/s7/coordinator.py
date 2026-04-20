"""Data update coordinator for the s7 integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from s7 import Client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class S7Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the PLC for configured tag values."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        host: str,
        rack: int,
        slot: int,
        port: int,
        password: str | None,
        use_tls: bool,
        tags: list[str],
        scan_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({host})",
            update_interval=scan_interval,
        )
        self._client = Client()
        self._host = host
        self._rack = rack
        self._slot = slot
        self._port = port
        self._password = password
        self._use_tls = use_tls
        self._tags = tags

    @property
    def host(self) -> str:
        return self._host

    @property
    def tags(self) -> list[str]:
        return self._tags

    async def async_connect(self) -> None:
        """Open the PLC connection (run in executor — snap7 is blocking)."""

        def _connect() -> None:
            self._client.connect(
                self._host,
                self._rack,
                self._slot,
                self._port,
                use_tls=self._use_tls,
                password=self._password,
            )

        await self.hass.async_add_executor_job(_connect)

    async def async_disconnect(self) -> None:
        if self._client.connected:
            await self.hass.async_add_executor_job(self._client.disconnect)

    async def _async_update_data(self) -> dict[str, Any]:
        """Read all configured tags and return a dict keyed by tag string."""

        def _read() -> dict[str, Any]:
            if not self._client.connected:
                self._client.connect(
                    self._host,
                    self._rack,
                    self._slot,
                    self._port,
                    use_tls=self._use_tls,
                    password=self._password,
                )
            values = self._client.read_tags(self._tags)
            return dict(zip(self._tags, values, strict=True))

        try:
            return await self.hass.async_add_executor_job(_read)
        except Exception as err:
            raise UpdateFailed(f"Failed to read PLC tags: {err}") from err

    async def async_write_tag(self, tag: str, value: Any) -> None:
        """Write a single tag value to the PLC."""

        def _write() -> None:
            self._client.write_tag(tag, value)

        await self.hass.async_add_executor_job(_write)
        # Trigger a refresh so entities reflect the new value
        await self.async_request_refresh()
