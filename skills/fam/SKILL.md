---
name: fam
description: Personal CRM. Ranks people due for contact. Reads/writes plain markdown in user's Obsidian vault. Use when user asks "who should I reach out to", "log lunch with X", "snooze Y until next month", or any relationship-maintenance prompt.
---

# fam — Personal CRM

## Resolve context

For shorthand such as "mark the first one done" or "snooze number 2", read the relevant queue or reminder output before acting. If the context does not identify one person and action, ask the user.

## Prerequisites

- Obsidian app installed and running
- `obsidian` CLI enabled: Settings → General → Command line interface
- Templater plugin when `/fam-tend` creates stubs from `person_template`

Use the repo's CLI commands. Surface failures verbatim; do not assume every CLI error means the CLI is disabled.

## Vault contract

- People = `@<Name>.md` anywhere in the vault
- Config = `fam-circles.md` anywhere in the vault, with a unique filename
- Contact dates = bullets under `## Logged contacts` in a person note
- Bullet format = `- YYYY-MM-DD — <freetext>`
- Non-contact mentions = bullets under `## Other references`

Resolve the active Obsidian vault before locating config or people. `fam-circles.md` lives in the vault, not the repo. `FAM_VAULT_NAME` selects a registered vault. See [development guidance](../../docs/development.md) for automation path overrides.

## Config

`fam-circles.md` holds a fenced `yaml` block with a required `circles` mapping. Both fields below are required when `/fam-tend` finds unresolved `[[@Name]]` links:

- `people_folder: <vault-relative path>` — destination for stubs
- `person_template: <vault-relative path>` — Templater template

See [configuration](../../docs/DESIGN.md#configuration) for circle definitions and required entries.

Use static YAML frontmatter in the template. Do not use `processFrontMatter` or move the file inside the template; the caller sets the destination.

## Schema

Required:

- `circle: reference|passive|inner|close|orbit|distant`
  - `reference` = noted person, no contact intent, such as a public figure
  - `passive` = relationship maintained without cadence

Optional:

- `cadence_days_override: <positive int>`
- `snooze_until: <ISO date>` — hide until the date arrives
- `next_action_at: <ISO date>` — explicit due-date override
- `contact_channels_ordered_preference: [imessage, signal, email, ...]`
- `periodic_contact_reminders: false` — mute cadence-based reminders while keeping the person's circle. A person with a cadence still surfaces when `next_action_at` is set. Default `true`. Use for "stop nudging me about X" or "no periodic reminders for X".

Preserve the user's other frontmatter. Derive `last_contacted` from `## Logged contacts`; never store it in frontmatter.

Queue exclusion follows configured `cadence_days: null`. An explicit `next_action_at` does not override no-cadence exclusion.

## Commands

| Command | Use |
|---------|-----|
| `/fam-today` | Show ranked queue. Default includes scores at or above each circle's threshold. `--all` includes below-threshold rows, including people not yet due; exclusions still apply. `--circle X` filters, `--limit N` caps rows, `--json` returns structured output. `--include-snoozed` includes snoozed rows. Missing `circle` is persisted as `reference` under validation. |
| `/fam-tend` | Create stubs for unresolved `[[@Name]]` links using the configured template; sync the configured people index; add dated backlink bullets to `## Logged contacts` and summary placeholders to `## Other references`. `--person <name>` limits people tended. `--dry-run` previews without writing. Repeated runs do not duplicate generated entries. |
| `/fam-validate` | Check config and person notes. |

From the repo, use `uv run fam-tend`, `uv run fam-today`, and `uv run fam-validate`. From another directory, use `uv --project "<plugin-root>" run <command>`.

Mutating scripts validate the vault before and after work. Invalid config or person notes abort tending. Surface failed stub creation and validation errors before further edits.

## Log a contact

For "log a coffee with Christina yesterday, talked about her dog":

1. Resolve the person note. If multiple names match, ask which person.
2. Resolve the date from today's date: "yesterday" is one day earlier. Use an explicit date when supplied.
3. Append `- YYYY-MM-DD — coffee, talked about her dog` under `## Logged contacts`, replacing the date placeholder with the resolved ISO date.

## Clean up overrides

An expired `snooze_until` can be removed; the queue already ignores it once the date arrives.

Keep `next_action_at` until its associated action is completed or the user dismisses it. A passed date means overdue, not completed.

## Add a person

For "start tracking @Jane Doe, met her at climbing gym, close circle":

1. Check for an existing person note before creating one. Use the configured people folder or the user's existing layout.
2. Create `@Jane Doe.md` with `circle: close` and the two body sections: `## Logged contacts` and `## Other references`.
3. Log the meeting with the date supplied by the user. Ask for the date if needed; do not assume the meeting happened today.

See [example person](../../examples/@Jane%20Doe.md) and [person template](../../examples/person_template.md).

## After tending

After a successful mutating run, read linked notes and replace generated `TODO: summarize` placeholders in person notes touched by that run with one-sentence reasons the person appears. Keep each link's full vault-relative target.

Cleanup is limited to generated placeholders and exact duplicate generated bullets in those touched notes. Preserve user-written content. If ownership is unclear, leave the content and report it.

For `--dry-run`, present the preview without editing notes, frontmatter, summaries, or indexes.

## Errors

| Error | Fix |
|-------|-----|
| `obsidian: command not found` | Check Obsidian installation, CLI settings, and executable availability. |
| `fam-circles.md not found` | Verify the selected vault, config path, and process permissions before creating config. |
| `FAM_CIRCLES_PATH points to unreadable fam-circles.md` | Verify the path and process access; unreadable does not mean missing. |
| `multiple fam-circles.md found` | Report matching paths; ask the user which config to keep. |
| `unknown circle <X>` | Correct the circle name in frontmatter. |
| `cadence_days_override must be int > 0` | Correct or remove the field. |
| Stub creation fails | Surface the reported failures. Do not claim tending succeeded or raise timeouts without investigating. |

Surface errors verbatim to the user.
