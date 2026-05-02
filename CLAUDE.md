# prm-md — agent rules

This repo is a Claude Code plugin: a personal CRM driven from the agent.

## Where the design lives

`<vault>/wiki/People/plans/2026-05-01-prm-md-design.md`

Read it before making non-trivial changes. It owns the schema, the score model, and the command surface.

## Vault conventions

- Vault: `/home/ricardo/Documents/obsidian/`. Vault name (for `obsidian` CLI): `obsidian`.
- People notes: `wiki/People/@<Name>.md`.
- Meetings: `Journal/Meetings/<YYYY-MM-DD> Meeting <stuff>.md`. To associate a person, body wikilink `[[@Name]]`.
- Templater template: `Templates/Inputs/person_template.md`.
- Circle config: `wiki/People/circles.md` (YAML inside a fenced code block in the body).

## Obsidian CLI

- Always pass `vault="obsidian"`. Default may resolve to a stale registration.
- Never pass `--help` after a subcommand — destructive subcommands silently act on the active editor file.
- Verify Obsidian is running before issuing CLI calls (`obsidian version`); launch via `xdg-open obsidian://` if not.

## Architecture rules

- Scripts only encode cross-vault aggregation. Per-person CRUD is direct file editing.
- Every script wraps its work in `lib/validate.guard()` (preflight + postflight).
- `lib/vault.py` auto-injects `vault="obsidian"` for every `obsidian` CLI call.
- Pure-derived `last_contacted` — never store it in person frontmatter.

## Out of scope (MVP)

Channel send/read, channel-derived `last_contacted`, Nextcloud watcher, Bases generation, birthdays, concurrency/locking, multi-vault. See spec.
