# Develop fam

Install development dependencies and run checks from the repository root:

```shell
uv sync --locked --extra dev
uv run pytest
uv run ruff check .
uv run pyright scripts tests
```

Tests use synthetic notes in `tests/fixtures/vault/`. Mutating tests copy
the fixture through `vault_root`. They must not edit the source fixture or
your personal vault. Tests mock Obsidian responses; they don't verify the
running app or Templater.

The supported repository commands are console scripts:

```shell
uv run fam-today --json
uv run fam-tend --dry-run
uv run fam-validate
```

These commands operate on the selected Obsidian vault, even when you run them
from the repository. They don't look for `fam-circles.md` in the current
working directory. See [vault selection](DESIGN.md#vault-selection) for
environment overrides.

## Scheduled commands

Use absolute executable and project paths when the scheduler has a different
working directory or `PATH`. If the parent process sets `VIRTUAL_ENV` for
another environment, unset it before invoking `uv`.

`OBSIDIAN_VAULT_PATH` and `FAM_CIRCLES_PATH` avoid asking Obsidian for the
vault root or scanning for configuration. Creating notes through Templater
still needs Obsidian running. Keep deployment-specific paths in the scheduler
environment or local wrapper.

If a command can't read configuration, verify the selected path and the
scheduled process's file permissions. On macOS, that process might need Documents
access or Full Disk Access.
