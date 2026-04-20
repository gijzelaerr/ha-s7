"""Shared fixtures for the s7 integration tests.

Spins up a python-snap7 legacy server in a background thread so the
integration can exercise real read/write paths without a physical PLC.
"""

from __future__ import annotations

import random
import struct
import time
from collections.abc import Generator
from ctypes import c_char

import pytest

from snap7.server import Server as LegacyServer
from snap7.type import SrvArea


@pytest.fixture
def enable_custom_integrations(enable_custom_integrations):  # noqa: F811
    """Auto-enable loading `custom_components/` via pytest-homeassistant-custom-component."""
    yield


@pytest.fixture
def s7_server() -> Generator[tuple[LegacyServer, int, bytearray], None, None]:
    """Start a python-snap7 legacy S7 server pre-populated with DB1 test data.

    Yields (server, port, db1_data). The server runs for the lifetime of the
    test and is stopped at teardown.
    """
    server = LegacyServer()

    db1_data = bytearray(100)
    struct.pack_into(">f", db1_data, 0, 23.5)  # DB1.DBD0 = 23.5 (REAL)
    struct.pack_into(">h", db1_data, 4, 42)  # DB1.DBW4 = 42 (INT)
    db1_data[6] = 0x01  # DB1.DBB6 bit 0 = 1 (BOOL)

    db1_buf = (c_char * 100).from_buffer(db1_data)
    server.register_area(SrvArea.DB, 1, db1_buf)

    # Writable DB for switch/number tests
    db2_data = bytearray(100)
    db2_buf = (c_char * 100).from_buffer(db2_data)
    server.register_area(SrvArea.DB, 2, db2_buf)

    port = random.randint(20000, 30000)
    server.start(tcp_port=port)
    time.sleep(0.2)

    yield server, port, db1_data

    server.stop()
    server.destroy()
