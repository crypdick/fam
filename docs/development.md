# Develop fam

Install development dependencies and run checks from the repository root:

```shell
uv sync --locked --extra dev
uv run pytest
uv run ruff check .
uv run pyright scripts tests tools
uv build
```

Tests use synthetic notes in `tests/fixtures/vault/`. Mutating tests copy the fixture through `vault_root`; never edit the source fixture or your personal vault. Obsidian responses are mocked. MCP tests cover tool calls and a local HTTP server with authentication.

Use one console script with subcommands:

```shell
uv run fam today --json
uv run fam list
uv run fam tend --dry-run
uv run fam validate
```

Commands use the selected Obsidian vault, not the working directory. See [vault selection](DESIGN.md#vault-selection) for environment overrides.

## Plugin releases

After checks pass for a push to `main`, CI increments the patch version from
`pyproject.toml`, synchronizes `.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, and `.codex-plugin/plugin.json`, and refreshes
`uv.lock`. It checks the release before pushing a `Release X.Y.Z` commit.
`tools/prepare_release.py` owns release version selection and manifest sync.

For a manual release, run `uv version --bump minor` (or `major` or `patch`),
update the three plugin manifests to the same version, and commit those files
with `uv.lock`. The metadata test requires versions to agree before release.
`pyproject.toml` is the version source of truth; CI preserves a version higher
than the branch version before the whole push, including a bump in an earlier
pushed commit. Decreased versions fail release preparation.

Feature branches and pull requests only run checks. Retries reuse the release
commit, and runs overtaken by another push skip release. Branch rules must allow
the GitHub Actions bot to push release commits using `GITHUB_TOKEN`.

## Scheduled commands

Use absolute executable and project paths when the scheduler has a different
working directory or `PATH`. If the parent process sets `VIRTUAL_ENV` for
another environment, unset it before invoking `uv`.

Set `OBSIDIAN_VAULT_PATH` and `FAM_CIRCLES_PATH` to avoid CLI vault discovery and configuration scanning. The default Templater creation backend still needs Obsidian running. Use the explicit [headless creation backend](DESIGN.md#creation) for static templates in unattended deployments. Keep deployment paths in the scheduler environment or local wrapper.

If a command can't read configuration, verify the selected path and the
scheduled process's file permissions. On macOS, that process might need Documents
access or Full Disk Access.
