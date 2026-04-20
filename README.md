# ha-s7

Home Assistant integration for Siemens S7 PLCs (S7-300, S7-400, S7-1200, S7-1500, Logo).

Uses the [python-snap7](https://github.com/gijzelaerr/python-snap7) library's new `s7` package with automatic protocol detection (S7CommPlus for modern PLCs, legacy S7 otherwise) — no native dependencies required.

## Features

- Poll any PLC tag as a sensor, binary_sensor, switch, or number
- PLC4X / Siemens STEP7-style tag addressing (`DB1.DBD0:REAL`, `M10.5:BOOL`, `I0.0:BOOL`)
- Supports all S7 data types: BOOL, INT, REAL, STRING, DATE, DTL, ...
- TLS support for S7-1200/1500 V2/V3
- Configurable scan interval
- Automatic entity type selection based on tag datatype and area

## Installation

### Via HACS (recommended)

1. In HACS, add this repository as a custom repository (category: Integration).
2. Install "Siemens S7 PLC".
3. Restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration** and search for "Siemens S7 PLC".

### Manual

Copy `custom_components/s7/` into your Home Assistant `config/custom_components/` directory and restart.

## Configuration

During setup you provide:

- **Host** — PLC IP address
- **Rack / Slot** — usually 0 / 1 for S7-1200/1500, varies for S7-300/400
- **Port** — 102 by default
- **Use TLS** — required for S7-1200/1500 with firmware V2.9+/V4.3+
- **Password** — optional PLC legitimation password (TLS required)
- **Tags** — comma or newline-separated list of PLC4X-style tag addresses:
  ```
  DB1.DBD0:REAL
  DB1.DBX4.0:BOOL
  M10.5:BOOL
  I0.0:BOOL
  DB1:10:STRING[20]
  ```

## Entity mapping

| Tag area + type | Entity platform | Example tag |
|---|---|---|
| BOOL in I (input) | `binary_sensor` | `I0.0:BOOL` |
| BOOL in DB / M / Q | `switch` | `DB1.DBX4.0:BOOL` |
| Numeric readable | `sensor` | `DB1.DBD0:REAL` |
| Numeric in DB / M / Q | `number` (writable) | `DB1.DBW6:INT` |
| STRING / DATE / TIME | `sensor` | `DB1:10:STRING[20]` |

## Services

### `s7.write_tag`

Write any value to a PLC tag from an automation:

```yaml
service: s7.write_tag
data:
  entry_id: !config_entry_id
  tag: "DB1.DBW6:INT"
  value: 1500
```

## Requirements

- Home Assistant 2024.1 or later
- `python-snap7 >= 4.0.0` (installed automatically via the integration's `requirements`)
- PUT/GET enabled on the PLC, **or** a PLC that supports S7CommPlus

## License

MIT
