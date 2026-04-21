"""Data update coordinator for the s7 integration."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from snap7.tags import Tag, parse_tag

from s7 import Client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# snap7's Client is blocking and not thread-safe across concurrent
# operations, so we serialise all client access with a single asyncio lock.
# On connection loss we back off before retrying to avoid hot-looping on
# a PLC that stays down.
_RECONNECT_BACKOFF_SECONDS = (1.0, 2.0, 5.0, 10.0)


def parse_tags(inputs: list[str]) -> dict[str, Tag]:
    """Parse configured tag strings into Tag objects, keyed by original input.

    Accepts both PLC4X (``DB1.DBD0:REAL``) and nodeS7 (``DB1,R0``) syntax.
    Bare short forms like ``M7.1`` or ``IW22`` are accepted via
    ``parse_tag(..., strict=False)``.

    Raises ValueError listing every failed input.
    """
    parsed: dict[str, Tag] = {}
    errors: list[str] = []
    for raw in inputs:
        try:
            parsed[raw] = parse_tag(raw, strict=False, name=raw)
        except ValueError as err:
            errors.append(f"{raw!r}: {err}")
    if errors:
        raise ValueError("Invalid tag(s): " + "; ".join(errors))
    return parsed


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
        self._tag_strings = list(tags)
        self._parsed_tags = parse_tags(self._tag_strings)
        self._lock = asyncio.Lock()
        self._connect_failures = 0
        # Diagnostic metrics
        self._read_count = 0
        self._write_count = 0
        self._last_read_latency: float | None = None
        self._connected_since: datetime | None = None

    @property
    def host(self) -> str:
        return self._host

    @property
    def tags(self) -> list[str]:
        """Configured tag strings, in config order (used for unique IDs)."""
        return self._tag_strings

    @property
    def parsed_tags(self) -> dict[str, Tag]:
        """Parsed Tag objects keyed by original input string."""
        return self._parsed_tags

    @property
    def read_count(self) -> int:
        """Total successful read cycles since the coordinator was created."""
        return self._read_count

    @property
    def write_count(self) -> int:
        """Total successful write operations since the coordinator was created."""
        return self._write_count

    @property
    def last_read_latency(self) -> float | None:
        """Seconds taken by the most recent read cycle, or None if no cycle yet."""
        return self._last_read_latency

    @property
    def connected_since(self) -> datetime | None:
        """Timestamp of the last successful (re)connect, or None if never connected."""
        return self._connected_since

    async def async_connect(self) -> None:
        """Open the PLC connection (snap7 is blocking; runs in executor)."""
        async with self._lock:
            await self.hass.async_add_executor_job(self._blocking_connect)

    async def async_disconnect(self) -> None:
        async with self._lock:
            if self._client.connected:
                await self.hass.async_add_executor_job(self._client.disconnect)

    def _blocking_connect(self) -> None:
        self._client.connect(
            self._host,
            self._rack,
            self._slot,
            self._port,
            use_tls=self._use_tls,
            password=self._password,
        )
        self._connected_since = datetime.now(UTC)

    async def _async_update_data(self) -> dict[str, Any]:
        """Read all configured tags via the multi-variable optimizer."""

        def _read() -> dict[str, Any]:
            if not self._client.connected:
                self._blocking_connect()
            # Passing Tag objects lets the optimizer coalesce adjacent reads.
            tag_list = list(self._parsed_tags.values())
            values = self._client.read_tags(tag_list)
            return dict(zip(self._tag_strings, values, strict=True))

        async with self._lock:
            started = time.monotonic()
            try:
                result = await self.hass.async_add_executor_job(_read)
            except Exception as err:
                await self._async_mark_reconnect()
                raise UpdateFailed(f"Failed to read PLC tags: {err}") from err
            self._last_read_latency = time.monotonic() - started
            self._read_count += 1
            self._connect_failures = 0
            return result

    async def _async_mark_reconnect(self) -> None:
        """Drop the connection so the next cycle reconnects, with bounded backoff."""
        try:
            if self._client.connected:
                await self.hass.async_add_executor_job(self._client.disconnect)
        except Exception:  # noqa: BLE001
            pass
        idx = min(self._connect_failures, len(_RECONNECT_BACKOFF_SECONDS) - 1)
        delay = _RECONNECT_BACKOFF_SECONDS[idx]
        self._connect_failures += 1
        _LOGGER.debug("Reconnect backoff: %ss (failure #%d)", delay, self._connect_failures)
        await asyncio.sleep(delay)

    async def async_write_tag(self, tag_string: str, value: Any) -> None:
        """Write a value to the tag identified by its configured address string.

        Accepts both pre-configured tags (looked up from ``parsed_tags``) and
        arbitrary addresses passed via the ``write_tag`` service. Unknown
        strings are parsed on the fly via ``parse_tag(strict=False)``.
        """
        tag = self._parsed_tags.get(tag_string)
        if tag is None:
            tag = parse_tag(tag_string, strict=False, name=tag_string)

        def _write() -> None:
            if not self._client.connected:
                self._blocking_connect()
            self._client.write_tag(tag, value)

        async with self._lock:
            await self.hass.async_add_executor_job(_write)
            self._write_count += 1
        await self.async_request_refresh()

    async def async_pulse_tag(self, tag_string: str, duration: float) -> None:
        """Write True, wait ``duration`` seconds, write False.

        Used for momentary commands where the PLC expects a rising/falling
        edge (``start`` / ``acknowledge`` / ``reset`` buttons). The sleep is
        asynchronous so other coordinator work can still run; the
        client-level lock is released during the wait so reads are not
        blocked.
        """
        await self.async_write_tag(tag_string, True)
        await asyncio.sleep(duration)
        await self.async_write_tag(tag_string, False)
