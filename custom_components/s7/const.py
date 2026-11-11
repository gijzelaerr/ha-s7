"""Constants for the s7 integration."""

from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from homeassistant.const import Platform
from snap7.type import Area

DOMAIN = "s7"

# Config entry keys
CONF_HOST = "host"
CONF_RACK = "rack"
CONF_SLOT = "slot"
CONF_PORT = "port"
CONF_PASSWORD = "password"
CONF_USE_TLS = "use_tls"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TAGS = "tags"
CONF_PROTOCOL = "protocol"

# Wire protocols
PROTOCOL_LEGACY = "legacy"  # classic S7 (PUT/GET), all S7 CPUs
PROTOCOL_S7COMMPLUS = "s7commplus"  # S7-1200/1500 without PUT/GET
PROTOCOL_CHOICES = [PROTOCOL_LEGACY, PROTOCOL_S7COMMPLUS]

# Defaults
DEFAULT_PORT = 102
DEFAULT_RACK = 0
DEFAULT_SLOT = 1
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
DEFAULT_PROTOCOL = PROTOCOL_LEGACY


def plc_id(data: Mapping[str, Any]) -> str:
    """Identify one PLC. Rack and slot only select a CPU on the legacy protocol."""
    base = f"{data[CONF_HOST]}:{data.get(CONF_PORT, DEFAULT_PORT)}"
    if data.get(CONF_PROTOCOL, DEFAULT_PROTOCOL) == PROTOCOL_S7COMMPLUS:
        return base
    return f"{base}:{data.get(CONF_RACK, DEFAULT_RACK)}:{data.get(CONF_SLOT, DEFAULT_SLOT)}"


# Platforms this integration provides
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.TEXT,
]

# Areas a tag can be written in: data blocks, flags (M) and outputs (Q).
# Inputs (I) are read-only.
WRITABLE_AREAS = frozenset({Area.DB, Area.MK, Area.PA})

# Types that decode to an int or a float.
NUMERIC_TYPES = frozenset(
    {
        "BYTE",
        "SINT",
        "USINT",
        "INT",
        "UINT",
        "WORD",
        "DINT",
        "UDINT",
        "DWORD",
        "REAL",
        "LINT",
        "ULINT",
        "LWORD",
        "LREAL",
    }
)
FLOAT_TYPES = frozenset({"REAL", "LREAL"})
STRING_TYPES = frozenset({"STRING", "WSTRING", "FSTRING"})
CHAR_TYPES = frozenset({"CHAR", "WCHAR"})
TIME_TYPES = frozenset({"TIME", "LTIME", "S5TIME", "TOD", "LTOD", "DATE", "DT", "LDT", "DTL"})


def base_type(datatype: str) -> str:
    """Strip ``STRING[20]`` down to ``STRING``, in upper case."""
    return datatype.upper().split("[", 1)[0]


# States of the CPU state sensor; also its translation keys.
CPU_STATE_RUN = "run"
CPU_STATE_STOP = "stop"
