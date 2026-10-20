# Develop fam

Install development dependencies and run checks from the repository root:

```shell
uv sync --locked --extra dev
uv run pytest
uv run ruff check .
uv run pyright scripts tests
```

Tests use synthetic notes in `tests/fixtures/vault/`. Mutating tests copy the fixture through `vault_root`; never edit the source fixture or your personal vault. Obsidian responses are mocked. MCP tests cover tool calls and a local HTTP server with authentication.

Use one console script with subcommands:

```shell
uv run fam today --json
uv run fam tend --scan --dry-run
uv run fam validate
```

Commands use the selected Obsidian vault, not the working directory. See [vault selection](DESIGN.md#vault-selection) for environment overrides.

## Scheduled commands

Use absolute executable and project paths when the scheduler has a different
working directory or `PATH`. If the parent process sets `VIRTUAL_ENV` for
another environment, unset it before invoking `uv`.

Set `OBSIDIAN_VAULT_PATH` and `FAM_CIRCLES_PATH` to avoid CLI vault discovery and configuration scanning. Templater creation still needs Obsidian running. Keep deployment paths in the scheduler environment or local wrapper.

If a command can't read configuration, verify the selected path and the
scheduled process's file permissions. On macOS, that process might need Documents
access or Full Disk Access.
