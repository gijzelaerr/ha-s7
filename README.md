# ha-s7 — Home Assistant integration for Siemens S7 PLCs

[![Validate](https://github.com/gijzelaerr/ha-s7/actions/workflows/validate.yml/badge.svg)](https://github.com/gijzelaerr/ha-s7/actions/workflows/validate.yml)
[![Lint](https://github.com/gijzelaerr/ha-s7/actions/workflows/lint.yml/badge.svg)](https://github.com/gijzelaerr/ha-s7/actions/workflows/lint.yml)
[![Test](https://github.com/gijzelaerr/ha-s7/actions/workflows/test.yml/badge.svg)](https://github.com/gijzelaerr/ha-s7/actions/workflows/test.yml)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Read and write tags on a Siemens S7 PLC (S7-300, S7-400, S7-1200, S7-1500) as Home Assistant sensors, binary sensors, switches, numbers and text entities.

Two wire protocols are supported, both pure Python with no native dependencies:

- **Legacy S7 (PUT/GET)** via [python-snap7](https://github.com/gijzelaerr/python-snap7) — S7-300/400, and S7-1200/1500 with PUT/GET access enabled.
- **S7CommPlus** via [s7commplus](https://github.com/gijzelaerr/s7commplus) — S7-1200/1500 where PUT/GET is disabled (V1, V2 with TLS, V3).

---

## Features

- **S7-300/400/1200/1500** — classic S7 or S7CommPlus, no native libraries needed
- **Industry-standard addressing** — PLC4X / Siemens STEP7 syntax (`DB1.DBD0:REAL`, `M10.5:BOOL`, `I0.0:BOOL`)
- **Entities chosen automatically** from each tag's area and datatype:
  | Tag area | Datatype | Entities |
  |---|---|---|
  | `I` (input) | `BOOL` | `binary_sensor` |
  | `DB`, `M`, `Q` | `BOOL` | `switch` (writable) |
  | `DB`, `M`, `Q` | numeric | `sensor` + `number` (writable) |
  | `DB`, `M`, `Q` | `STRING`, `WSTRING` | `sensor` + `text` (writable) |
  | `I`, or any area | numeric, `DATE`, `TIME`, … | `sensor` (read-only) |
- **All S7 types** — `BOOL`, `BYTE`/`SINT`/`USINT`, `INT`/`UINT`/`WORD`, `DINT`/`UDINT`/`DWORD`, `REAL`, `LREAL`, `LINT`/`ULINT`, `STRING[n]`, `WSTRING[n]`, `DATE`, `TIME`, `TOD`, `DT`, `DTL`, `LDT`, `LTIME`, `LTOD`
- **Batched reads** — one multi-variable request per poll on both protocols
- **TLS + password authentication** — S7CommPlus V2/V3 on S7-1200/1500
- **Diagnostic sensors** — read/write counters, read latency and connected-since per PLC (disabled by default; enable them on the device page)
- **`write_tag` and `pulse_tag` services** for automations

## Installation

### HACS (recommended)

This repository is not in the default HACS list yet, so add it as a custom repository:

1. In HACS, open the menu (⋮) → **Custom repositories**.
2. Add `https://github.com/gijzelaerr/ha-s7` with category **Integration**.
3. Search for **Siemens S7 PLC** and download it.
4. Restart Home Assistant.
5. **Settings → Devices & Services → Add Integration** → *Siemens S7 PLC*.

Home Assistant installs the required Python packages (`python-snap7`, `s7commplus`) itself on the first start.

### Manual

Download the latest release from the [releases page](https://github.com/gijzelaerr/ha-s7/releases) and copy the `custom_components/s7` folder into your Home Assistant configuration directory, so that you end up with `<config>/custom_components/s7/manifest.json`. Restart Home Assistant, then add the integration as above.

## Configuration

The integration is configured entirely through the HA UI. During setup:

| Field | Description | Default |
|---|---|---|
| Host | PLC IP address | — |
| Rack | Rack number (usually 0 for S7-1200/1500) | `0` |
| Slot | Slot number (usually 1 for S7-1200/1500) | `1` |
| TCP port | S7 port | `102` |
| Protocol | `legacy` (classic S7 / PUT/GET) or `s7commplus` (S7-1200/1500) | `legacy` |
| Use TLS | S7CommPlus V2/V3 only (S7-1200 FW ≥ 4.3 / S7-1500 FW ≥ 2.9) | off |
| Password | PLC legitimation password (S7CommPlus only) | — |
| Tags | Newline- or semicolon-separated PLC4X or nodeS7 addresses | — |

Rack and slot are only used by the legacy protocol.

### Choosing a protocol

- **S7-300/400**: use `legacy`.
- **S7-1200/1500 with PUT/GET enabled** (TIA Portal → CPU properties → Protection & security → Connection mechanisms → "Permit access with PUT/GET communication from remote partner"): `legacy` works and is the best-tested path.
- **S7-1200/1500 with PUT/GET disabled**: use `s7commplus`, enable TLS and enter the PLC password where the firmware requires it. S7CommPlus support is new and has so far only been tested against an emulator, so please report problems.

On S7-1200/1500, tags are addressed by absolute byte offset, so each data block you read must have **"Optimized block access" turned off**. Symbolic access to optimized blocks is not supported yet.

The **scan interval** (default 30 s) and the **tag list** can be changed later via the integration's *Configure* (options) dialog. Saving reloads the integration, and entities of removed tags are deleted. Array tags (for example `REAL[5]`) are not supported and are rejected.

### Example tag list

```
DB1.DBD0:REAL
DB1.DBW4:INT
DB1.DBX6.0:BOOL
M10.5:BOOL
I0.0:BOOL
Q0.0:BOOL
DB1:10:STRING[20]
DB1,R8
```

See [python-snap7's tag docs](https://python-snap7.readthedocs.io/en/latest/API/tags.html) for the full address syntax.

## Services

Both services take the `entry_id` of the PLC's config entry (a long ID string, found in `.storage/core.config_entries` in your configuration directory). `tag` accepts any PLC4X or nodeS7 address, whether or not it is configured as an entity.

### `s7.write_tag`

```yaml
service: s7.write_tag
data:
  entry_id: "<config entry id>"
  tag: "DB1.DBW6:INT"
  value: 1500
```

### `s7.pulse_tag`

Writes `True`, waits, then writes `False` — for momentary commands such as start or acknowledge.

```yaml
service: s7.pulse_tag
data:
  entry_id: "<config entry id>"
  tag: "M10.0:BOOL"
  duration: 0.5
```

## Requirements

- Home Assistant ≥ 2024.12
- Python ≥ 3.13
- python-snap7 ≥ 3.2.1 and s7commplus ≥ 0.1.0 (installed automatically by Home Assistant)

## Development

```bash
git clone https://github.com/gijzelaerr/ha-s7
cd ha-s7
uv sync --group dev
uv run pre-commit install
uv run pytest
```

The tests spin up the python-snap7 and s7commplus server emulators and exercise the full config flow → coordinator → entity chain. No physical PLC is required. The Home Assistant test harness only runs on Linux/macOS; on Windows use WSL.

## License

MIT — see [LICENSE](LICENSE).
