# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed
- A tag the PLC cannot read, such as one in a data block that does not exist, makes only its own entities unavailable instead of all of them. The tag is logged once, and again when it can be read.
- More than 20 tags on the classic S7 protocol no longer makes setup and every poll fail; the tags are read in groups of 20.
- The tags field in setup and Configure is a multi-line box, so tags can be entered one per line, and a failed setup step keeps what was entered instead of clearing the tag list. (#63)

## [0.2.0] - 2026-11-08

### Fixed
- The options form requires a positive scan interval; a negative one polled the PLC in a tight loop. (#42)
- The config flow closes its test connection when the test read fails. (#43)
- An address listed twice no longer makes setup retry forever. (#44)
- Tags whose type has no known size, such as `STRING` without a length, are refused when entered, instead of failing every poll. (#45)
- Failed writes raise Home Assistant errors that name the tag. (#46)
- `write_tag` keeps text such as `123` or `on` as text on string tags, and `pulse_tag` refuses anything but a BOOL. (#47)
- `pulse_tag` releases the bit when the pulse is cancelled and retries a failed release. (#48)
- String values over 255 characters show their start instead of `unknown`, and their text entity is created. (#49)
- REAL values show as the number the PLC holds: 23.1, not 23.1000003814697. (#50)
- REAL and LREAL number entities have a fractional step, and large integers stay exact. (#51)
- PLCs on one host keep their own entities and device, and two slots behind one address can both be added. Existing entries migrate and keep their entity IDs. (#52)
- Debug logging includes `s7commplus`. (#53)
- Requires `python-snap7` 3.4.0 and uses its public tag codec instead of private helpers. `S5TIME` tags are accepted and shown as a sensor; they can't be written yet. (#53, #58)
- Requires `s7commplus` 0.4.0: writes and subscriptions work on an S7-1200 without TLS, and a request that times out ends the session so the next poll reconnects. (#59)

## [0.1.4] - 2026-10-21

### Fixed
- Setup raises `ConfigEntryNotReady` when the PLC is unreachable at startup, so Home Assistant retries instead of leaving the entry in a setup error.

## [0.1.3] - 2026-10-13

### Changed
- Config and service schemas use `probatio` (as in current Home Assistant) instead of `voluptuous`.
- Dev dependencies updated (`pytest-homeassistant-custom-component` 0.13.371, `s7commplus` 0.2.0).

## [0.1.2] - 2026-10-06

### Added
- Integration icon and logo (`assets/`, and `custom_components/s7/brand/` for Home Assistant).
- The HACS validation now runs without ignoring the brands check.

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

[Unreleased]: https://github.com/gijzelaerr/ha-s7/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/gijzelaerr/ha-s7/compare/v0.1.4...v0.2.0
[0.1.4]: https://github.com/gijzelaerr/ha-s7/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/gijzelaerr/ha-s7/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/gijzelaerr/ha-s7/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/gijzelaerr/ha-s7/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/gijzelaerr/ha-s7/releases/tag/v0.1.0
