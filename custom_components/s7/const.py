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

# Protocol selection values — match s7._protocol.Protocol names.
PROTOCOL_AUTO = "AUTO"
PROTOCOL_LEGACY = "LEGACY"
PROTOCOL_S7COMMPLUS = "S7COMMPLUS"
PROTOCOL_CHOICES = [PROTOCOL_AUTO, PROTOCOL_LEGACY, PROTOCOL_S7COMMPLUS]

# Defaults
DEFAULT_PORT = 102
DEFAULT_RACK = 0
DEFAULT_SLOT = 1
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
DEFAULT_PROTOCOL = PROTOCOL_AUTO

# Platforms this integration provides
PLATFORMS = ["sensor", "binary_sensor", "switch", "number", "text"]
