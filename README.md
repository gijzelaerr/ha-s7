# ha-s7 — Home Assistant integration for Siemens S7 PLCs

[![Validate](https://github.com/gijzelaerr/ha-s7/actions/workflows/validate.yml/badge.svg)](https://github.com/gijzelaerr/ha-s7/actions/workflows/validate.yml)
[![Lint](https://github.com/gijzelaerr/ha-s7/actions/workflows/lint.yml/badge.svg)](https://github.com/gijzelaerr/ha-s7/actions/workflows/lint.yml)
[![Test](https://github.com/gijzelaerr/ha-s7/actions/workflows/test.yml/badge.svg)](https://github.com/gijzelaerr/ha-s7/actions/workflows/test.yml)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Read and write any tag on a Siemens S7 PLC (S7-300, S7-400, S7-1200, S7-1500, Logo) as Home Assistant sensors, binary_sensors, switches, and numbers.

Built on [python-snap7](https://github.com/gijzelaerr/python-snap7) 4.0's unified `s7` package — pure Python, no native dependencies, automatic protocol detection (S7CommPlus for modern PLCs, classic S7 otherwise), TLS support for S7-1200/1500 V2/V3.

---

## Features

- **Any S7 PLC** — works with S7-300/400/1200/1500 and Logo, no native libraries needed
- **Industry-standard addressing** — PLC4X / Siemens STEP7 syntax (`DB1.DBD0:REAL`, `M10.5:BOOL`, `I0.0:BOOL`)
- **Four entity platforms** automatically mapped by tag datatype + area:
  | Tag area | Datatype | Platform |
  |---|---|---|
  | `I` (input) | `BOOL` | `binary_sensor` |
  | `DB`, `M`, `Q` | `BOOL` | `switch` |
  | `DB`, `M`, `Q` | numeric | `number` (writable) |
  | any | numeric, `STRING`, `DATE`, … | `sensor` |
- **All S7 types** — `BOOL`, `BYTE`/`SINT`/`USINT`, `INT`/`UINT`/`WORD`, `DINT`/`UDINT`/`DWORD`, `REAL`, `LREAL`, `LINT`/`ULINT`, `STRING[n]`, `WSTRING[n]`, `DATE`, `TIME`, `TOD`, `DT`, `DTL`, `LDT`, `LTIME`, `LTOD`, and arrays
- **Batched reads** — uses python-snap7's multi-variable read optimizer to minimize PDU round-trips
- **TLS + password authentication** — for S7-1200/1500 V2/V3
- **`write_tag` service** for automations

## Installation

### HACS (recommended)

1. In HACS, **Settings → Custom repositories**, add `https://github.com/gijzelaerr/ha-s7` with category **Integration**.
2. Install **Siemens S7 PLC**.
3. Restart Home Assistant.
4. **Settings → Devices & Services → Add Integration** → search for *Siemens S7 PLC*.

### Manual

```bash
cd ~/.homeassistant/custom_components
git clone https://github.com/gijzelaerr/ha-s7.git tmp
mv tmp/custom_components/s7 s7
rm -rf tmp
```

Restart Home Assistant.

## Configuration

The integration is configured entirely through the HA UI. During setup:

| Field | Description | Default |
|---|---|---|
| Host | PLC IP address | — |
| Rack | Rack number (usually 0 for S7-1200/1500) | `0` |
| Slot | Slot number (usually 1 for S7-1200/1500) | `1` |
| TCP port | S7 port | `102` |
| Use TLS | Required for S7-1200 FW ≥ 4.3 / S7-1500 FW ≥ 2.9 | off |
| Password | PLC legitimation password (TLS only) | — |
| Tags | Comma- or newline-separated PLC4X-style addresses | — |

**Scan interval** is configurable via the integration's *Options* menu (default 30 s).

### Example tag list

```
DB1.DBD0:REAL
DB1.DBW4:INT
DB1.DBX6.0:BOOL
M10.5:BOOL
I0.0:BOOL
Q0.0:BOOL
DB1:10:STRING[20]
DB2.DBD0:REAL[5]
```

See [python-snap7's tag docs](https://python-snap7.readthedocs.io/en/latest/API/tags.html) for the full syntax.

## Services

### `s7.write_tag`

```yaml
service: s7.write_tag
data:
  entry_id: !config_entry_id
  tag: "DB1.DBW6:INT"
  value: 1500
```

## Requirements

- Home Assistant ≥ 2024.12
- Python ≥ 3.13
- python-snap7 ≥ 4.0 (released to PyPI once 4.0 ships; until then `ha-s7` is developed against master)
- On the PLC: PUT/GET enabled **or** an S7-1200/1500 supporting S7CommPlus

## Development

```bash
git clone https://github.com/gijzelaerr/ha-s7
cd ha-s7
uv pip install -e ".[dev]"
pre-commit install
pytest
```

Tests spin up python-snap7's built-in S7 server emulator and exercise the full config-flow → coordinator → entity platform chain. No physical PLC required.

## License

MIT — see [LICENSE](LICENSE).
