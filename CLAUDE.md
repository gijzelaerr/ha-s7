# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repo.

## Project

Home Assistant custom integration for Siemens S7 PLCs, backed by
`python-snap7` (>=3.2.1, classic S7) and `s7commplus` (S7CommPlus for
S7-1200/1500). Not a Python package — HA's custom-component
loader owns the namespace. `pyproject.toml` has `[tool.uv] package =
false` and a PEP 735 dependency-groups layout for dev tooling.

## Contribution rules

- **Always run `uv run pre-commit run --all-files` before every `git push`.**
  Individual `ruff check` / `ruff format --check` don't exercise every
  hook (`ruff format` is the one that actually reformats files, not
  `--check`). Skipping pre-commit is the single most common reason CI
  fails on the ruff-format hook right after a push. If a hook reformats,
  amend and re-push — do not rely on "it passed locally" via other
  commands.
- Small, focused PRs. One concern per PR.
- `mypy custom_components` and `ruff check custom_components tests` must
  pass.
- Tests: `uv run pytest -v`. The fixtures spin up real `python-snap7` and
  `s7commplus` server emulators; the HA test harness needs `fcntl`, so on
  Windows run pytest under WSL. No mocks of the PLC protocol — no mocks of the PLC protocol.

## Architecture quick facts

- `custom_components/s7/plc.py` wraps both protocols behind one `PlcClient`
  interface (`create_client(protocol, ...)`); the coordinator never touches
  snap7/s7commplus directly. S7CommPlus uses absolute byte-offset access only.
- `custom_components/s7/coordinator.py` parses configured tag strings
  once (both PLC4X and nodeS7 syntax) via `parse_tag(..., strict=False)`
  and hands `Tag` objects to `client.read_tags()` (python-snap7's optimizer
  coalesces adjacent reads on the legacy path).
- Platforms classify entities by `tag.datatype` / `tag.area`, not by
  parsing strings.
- `services.py` registers `s7.write_tag` and `s7.pulse_tag` globally
  (not per-entry).
- Releases: bump `manifest.json` version, add a `CHANGELOG.md` entry, tag
  `vX.Y.Z` and publish a GitHub release (HACS installs from releases).
