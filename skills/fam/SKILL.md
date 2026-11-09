---
name: fam
description: Manage FAM person notes, contact logs, cadence, snoozes, and the contact queue in an Obsidian vault.
---

# FAM personal CRM

Maintain accurate relationship notes and useful reminders. Use [fam-review](../fam-review/SKILL.md) for interactive reviews and [fam-garden](../fam-garden/SKILL.md) for unattended preparation.

## Vault and tools

Follow applicable vault instructions and resolve the selected vault before editing. Person notes are `@Name.md` anywhere in the vault; configuration lives in the unique `fam-circles.md`. See [vault selection](../../docs/DESIGN.md#vault-selection) for `FAM_VAULT_NAME` and path overrides.

Prefer the `fam` CLI for contact logs and fam fields; use [FAM MCP tools](../../docs/MCP.md#tools) when CLI access is unavailable. Edit files directly for free-form relationship context. Preserve unrelated frontmatter, note content, reminder preferences, and no-contact boundaries. Use exact discovered paths; resolve ambiguous identities or shorthand before writing.

From the repository, run `uv run fam …`; elsewhere use `uv run --project "PLUGIN_ROOT" fam …` with the repository path. Core commands:

- `fam list`: all people, including inactive circles, snoozed people, and muted reminders. Supports metadata filters and `--sort score`.
- `fam today`: contacts, one-off actions, triage, and events in separate lists. An empty or filtered queue does not prove no matching people exist; check `fam list` and relevant notes. Below-threshold suggestions can appear when nobody is due; negative scores mean early.
- `fam events`: event reminders; `--days N` previews upcoming reminder windows.
- `fam person show PATH`: original note and summary.
- `fam person ensure "Name"`: create a missing note from the configured template. Check for existing notes anywhere in the vault; without a configured template, use the [person template](../../examples/person_template.md) in the existing vault layout.
- `fam tend --dry-run`: preview bulk creation from unresolved `[[@Name]]` links. Review candidates before running without `--dry-run`; tending needs no summaries or index maintenance.
- `fam person update PATH`: set fam fields; repeat `--clear FIELD` to remove optional fields.
- `fam validate`: check configuration and person notes.

Use command help or [design reference](../../docs/DESIGN.md) for flags, schemas, scoring, and output details. Read [creation setup](../../docs/DESIGN.md#creation) when configuring templates or choosing Templater versus headless creation. Templates need static YAML frontmatter; the caller controls destination.

Writes validate configuration and affected notes before and after changes; unrelated invalid notes do not block local repairs. Use `fam validate` for whole-vault health. Surface errors verbatim and resolve failures before continuing affected writes; inspect partial creation failures. Check vault selection, paths, and permissions before treating unreadable configuration as missing or assuming the CLI is disabled. Postflight failure does not roll back writes.

## Contact history and context

Log only an actual interaction established by the user's report or source evidence. Mentions, backlinks, dated filenames, calendar entries, and proposed outreach alone are insufficient. Establish the date in the user's time zone; ask if unknown rather than assuming today.

```shell
fam person log-contact PATH --date YYYY-MM-DD --description "Context"
```

Log one meaningful conversation or shared activity, not every message. Use a short, single-line paraphrase of substance and outcome. Exact date/description retries deduplicate; distinguish separate same-day interactions. Add `--complete-action` only when the interaction completes the pending action.

`## Logged contacts` is the source of truth for derived `last_contacted`; never store it in frontmatter. Missing history does not prove no contact occurred. Separate trackers should link to person notes, not duplicate contact history.

Use relevant, separately authorized sources to distill useful relationship context under `## Other references`, not archive messages. Quote only when wording matters to a boundary, promise, or decision. Separate impressions and unresolved questions from facts; avoid diagnoses and unsupported sensitive inferences. Imports and mentions establish neither friendship interest nor contact intent.

## Relationship choices and reminders

Record clear agreed plans, promised follow-ups, and supported important dates without extra approval. Assume Ricardo wants to make plans unless he explicitly says otherwise and that boundary is recorded in the person note. Unknown metadata stays unknown; preserve existing values when adding supported location, relationship tags, or interaction preferences.

Use configured circles. New, unclassified, or missing-circle records use `needs-triage` until user choice or evidence supports a substantive circle. `reference` means no contact intent; `passive` means an explicit choice against recurring reminders. Repair a missing circle with `fam person update PATH --circle needs-triage`, not a guessed relationship classification.

Keep one-off actions separate from recurring cadence:

- Circle changes preserve `cadence_days_override`.
- `snooze_until` hides reminders until its date. `periodic_contact_reminders: false` mutes cadence, not explicit one-off actions or events.
- Keep overdue `next_action_at` dates until completed or dismissed. Clear the date when logging the intended contact. While set, the action suppresses recurring cadence. Triage people appear in `triage`; other explicit actions appear in `actions`, independent of cadence thresholds.

For scheduled MCP queues, pass `on_date` in the user's time zone; the server defaults to its own local date.

Use `important_events` for birthdays, anniversaries, and one-off dates. Preserve known precision: `MM-DD` for annual dates, `YYYY-MM-DD` for one-offs; never invent a birth year. Ask when identity or date meaning is materially ambiguous. Read existing events before `fam person update PATH --important-events JSON` or MCP `update_person`: both replace the whole list. Preserve unrelated events; `--clear important_events` removes all. Events respect snoozes, work without cadence, and remain independent of contact logging. See [event schema and recurrence](../../docs/DESIGN.md#important-events) when setting reminders.

## Identity and external actions

Propose likely duplicate records to Ricardo with exact paths and evidence; confirm the match before consolidating identity. After confirmation, add alternate names to canonical `aliases` and cross-link the other record under `## Other references`. Preserve both records unless a merge or deletion is explicitly requested. Record rejected matches with enough disambiguation to avoid repeating them.

FAM does not read or send messages. External sources require separate authorization; report unavailable sources. Relationship maintenance and reminders do not authorize messages, invitations, reactions, or message edits.
