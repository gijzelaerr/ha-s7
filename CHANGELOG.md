# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.1] - 2026-10-06

### Added
- Edit the tag list (not just the scan interval) from the integration's options dialog; entities of removed tags are cleaned up.
- The connection error now hints at PUT/GET and "Optimized block access".

### Changed
- Array tags (for example `REAL[5]`) are rejected during validation instead of producing broken entities.
- Development environment moved to Python 3.14 and the dev lockfile updated to patched dependency versions.

## [0.1.0] - 2026-10-06

First release.

### Added
- Config flow for Siemens S7 PLCs: host, rack, slot, TCP port, protocol, TLS, password and tag list, with a connection test. Scan interval is set in the options flow (default 30 s).
- Two wire protocols behind one interface:
  - `legacy`: classic S7 (PUT/GET) via [python-snap7](https://github.com/gijzelaerr/python-snap7) for S7-300/400 and S7-1200/1500 with PUT/GET enabled.
  - `s7commplus`: S7CommPlus (V1/V2/V3, optional TLS and password) via [s7commplus](https://github.com/gijzelaerr/s7commplus) for S7-1200/1500 with PUT/GET disabled.
- Tag addressing in PLC4X (`DB1.DBD0:REAL`, `M10.5:BOOL`) and nodeS7 (`DB1,R0`, `IW22`) syntax.
- Entity platforms chosen from each tag's area and datatype: `sensor`, `binary_sensor`, `switch`, `number` and `text`.
- Batched reads: one multi-variable request per poll on both protocols.
- Services `s7.write_tag` and `s7.pulse_tag`.
- Diagnostic sensors (disabled by default): read count, write count, last read latency and connected-since.
- Automatic reconnect with bounded backoff when the PLC connection drops.
- Test suite running against the python-snap7 and s7commplus server emulators.

### Known limitations
- S7CommPlus has only been tested against an emulator, not a physical PLC. TLS and password authentication, and the M/I/Q areas over S7CommPlus, are untested.
- Tags use absolute byte-offset addressing. On S7-1200/1500, data blocks must have "Optimized block access" turned off; symbolic access to optimized blocks is not implemented.

[Unreleased]: https://github.com/gijzelaerr/ha-s7/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/gijzelaerr/ha-s7/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/gijzelaerr/ha-s7/releases/tag/v0.1.0
