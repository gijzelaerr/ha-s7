# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repo.

## Project

Home Assistant custom integration for Siemens S7 PLCs, backed by
`python-snap7` (>=4.0). Not a Python package — HA's custom-component
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
- Tests: `uv run pytest -v`. The fixture spins up a real `python-snap7`
  server emulator — no mocks of the PLC protocol.

## Architecture quick facts

- `custom_components/s7/coordinator.py` parses configured tag strings
  once (both PLC4X and nodeS7 syntax) via `parse_tag(..., strict=False)`
  and hands `Tag` objects to `client.read_tags()` so python-snap7's
  optimizer can coalesce adjacent reads.
- Platforms classify entities by `tag.datatype` / `tag.area`, not by
  parsing strings.
- `services.py` registers `s7.write_tag` and `s7.pulse_tag` globally
  (not per-entry).
