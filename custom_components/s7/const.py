"""Constants for the s7 integration."""

from datetime import timedelta

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

# Platforms this integration provides
PLATFORMS = ["sensor", "binary_sensor", "switch", "number", "text"]
