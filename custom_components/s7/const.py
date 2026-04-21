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

# Defaults
DEFAULT_PORT = 102
DEFAULT_RACK = 0
DEFAULT_SLOT = 1
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

# Platforms this integration provides
PLATFORMS = ["sensor", "binary_sensor", "switch", "number", "text"]
