# fam — agent rules

This repo is a Claude Code plugin: a personal CRM driven by an agent on top of plain-markdown person notes inside an Obsidian vault.

## Where the design lives

`<vault>/wiki/People/plans/2026-05-01-fam-design.md`

Read before non-trivial changes. It owns the schema, the score model, and the command surface.

## Conventions

- People = `@<Name>.md` anywhere in vault. No `wiki/People/` requirement.
- Config = `fam-circles.md` (unique filename) anywhere in vault.
- Source of truth for contact dates = bullets under `## Logged contacts`.
- Non-meeting mentions = bullets under `## Other references`.
- `obsidian` CLI is duck-typed — call it; if it fails, surface the error.
- All `obsidian` CLI calls go through `lib/vault.py` which auto-injects `vault=$FAM_VAULT_NAME` if set.

## Architecture rules

- Scripts encode only cross-vault aggregation. Per-person CRUD is direct file editing.
- Every mutating script wraps work in `lib/validate.guard()` (preflight + postflight).
- Pure-derived `last_contacted` from `## Logged contacts`. Never store it in frontmatter.
- Plugin owns only the `fam`-namespace fields. User-namespace frontmatter passes through.

## Out of scope (MVP)

Channel send/read, channel-derived `last_contacted`, Nextcloud watcher, Bases generation, birthdays, concurrency/locking, multi-vault. See spec.

## Tests

- `uv run pytest` runs all unit + light integration tests.
- Tests use `tests/fixtures/vault/` (synthetic, no real names). Mutating tests copy via `vault_root` conftest fixture.
- One integration marker (`@pytest.mark.integration`) for tests that hit the real `obsidian` CLI.
