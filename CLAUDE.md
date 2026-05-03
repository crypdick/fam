# fam — agent rules

Claude Code plugin. Personal CRM. Agent-driven, on top of plain-markdown person notes inside Obsidian vault.

## Design

[`docs/DESIGN.md`](docs/DESIGN.md). Read before non-trivial changes. Owns schema, score model, command surface.

## Conventions

- People = `@<Name>.md` anywhere in vault. No `wiki/People/` requirement.
- Config = `fam-circles.md` (unique filename) anywhere in vault.
- Contact-date source of truth = bullets under `## Logged contacts`.
- Non-meeting mentions = bullets under `## Other references`.
- `obsidian` CLI duck-typed — call it; failure → surface error.
- All `obsidian` CLI calls go through `lib/vault.py`, auto-injects `vault=$FAM_VAULT_NAME` if set.

## Architecture rules

- Scripts encode cross-vault aggregation only. Per-person CRUD = direct file edits.
- Every mutating script wraps work in `lib/validate.guard()` (preflight + postflight).
- `last_contacted` pure-derived from `## Logged contacts`. Never store in frontmatter.
- Plugin owns `fam`-namespace fields only. User-namespace frontmatter passes through.

## Out of scope (MVP)

Channel send/read, channel-derived `last_contacted`, Nextcloud watcher, Bases generation, birthdays, concurrency/locking, multi-vault. See spec.

## Tests

- `uv run pytest` runs all unit + light integration tests.
- Tests use `tests/fixtures/vault/` (synthetic, no real names). Mutating tests copy via `vault_root` conftest fixture.
- One integration marker (`@pytest.mark.integration`) for tests hitting real `obsidian` CLI.
