---
name: fam
description: Manage FAM person notes, contact logs, cadence, snoozes, and the contact queue in an Obsidian vault.
---

# FAM personal CRM

Use this skill for direct note operations. Use [fam-review](../fam-review/SKILL.md) for interactive relationship reviews and [fam-garden](../fam-garden/SKILL.md) for unattended preparation.

## Vault contract

Read applicable vault instructions and resolve the selected vault before editing. Person notes are `@Name.md` anywhere in the vault. The unique `fam-circles.md` file contains configuration. `FAM_VAULT_NAME` selects a registered vault; see [vault selection](../../docs/DESIGN.md#vault-selection) for path overrides.

Preserve unrelated frontmatter and note content, reminder preferences, and no-contact boundaries. Circle changes do not clear person-specific cadence overrides. Confirm identity before merging name variants. Resolve shorthand such as "snooze number 2" from the relevant queue or reminder before acting; ask if ambiguous.

Person notes are the source of truth for contact history. Link to them from any separate tracker. Keep hypotheses separate from confirmed facts. Imports and mentions do not establish friendship interest, and unanswered questions remain unresolved.

## Tools and commands

Use the CLI or available [FAM MCP tools](../../docs/MCP.md#tools). MCP tools may have a `fam_` prefix. Use these operations for contact logs and fam fields; use file tools for free-form relationship context.

- `fam list` shows all people as a table, sorted by name, including inactive circles, snoozes, and muted reminders. Use `--circle NAME`, `--location TEXT`, `--tag TAG`, `--interaction VALUE`, `--limit N`, or `--json`. Location uses a case-insensitive substring; tag and mode use whole-list membership. Filters combine before the limit. MCP equivalent: `list_people`.
- `fam today` is shorthand for `fam list --today`: the ranked contact queue without writes. It accepts the same filters plus `--all`, `--include-snoozed`, and `--on-date YYYY-MM-DD`. Filters retain all queue exclusions, even with `--all`. Missing circles fail validation; explicitly set the intended circle with `fam person update PATH --circle NAME`.
- `fam validate` checks configuration and person notes.
- `fam person show PATH` returns JSON with the original note. Use exact paths from the list or queue for writes.
- `fam person ensure "Jane Doe"` creates one named note through Templater if missing. `--dry-run` previews. MCP equivalent: `ensure_person`.
- `fam tend --dry-run` previews bulk creation from unresolved `[[@Name]]` links. Review candidates before rerunning without `--dry-run`. Existing notes stay unchanged; no summaries or index maintenance follow tending. MCP equivalent: `tend` with `dry_run: true`.
- `fam person log-contact PATH --date YYYY-MM-DD --description "Context"` records an evidenced interaction. Add `--complete-action` only when completing the pending action. MCP equivalent: `log_contact` with `on_date`.
- `fam person update PATH` sets fam fields through flags such as `--circle`, `--cadence-days-override`, `--snooze-until`, `--next-action-at`, `--no-periodic-contact-reminders`, `--contact-channels-ordered-preference signal email`, `--location TEXT`, `--relationship-tags friend family`, and `--interaction-preferences in_person call`. `--clear FIELD` removes an optional schema field; repeat for multiple removals. Circle cannot be cleared. MCP equivalent: `update_person` with field arguments and a `clear` list.

When nobody meets their alert threshold, `fam today` suggests up to 10
highest-ranked eligible people; `--limit N` overrides that count.
Filters and exclusions still apply. Negative
scores mean the suggestion is early. If nobody is eligible, table output
explains the empty result; JSON remains `[]`.

For the full directory ranked by score, use `fam list --sort score`, optionally
with `--on-date YYYY-MM-DD`. Scores appear in the table or JSON; filters and
sorting apply before `--limit`. Snoozed people and inactive circles remain
visible with score `-inf`; muted reminders keep their calculated scores.
MCP `list_people` accepts `sort_by: score` and optional `on_date`.

From the repository, prefix commands with `uv run`. Elsewhere use
`uv run --project "PLUGIN_ROOT" fam SUBCOMMAND ...`, replacing `PLUGIN_ROOT`
with the repository path.

CLI vault discovery needs Obsidian running with **Settings > General > Command line interface** enabled. Tending also needs Templater and the configured `people_folder` and `person_template`. Use static YAML frontmatter in templates; the caller sets the destination. See [configuration](../../docs/DESIGN.md#configuration) for setup.

Mutating scripts validate before and after writes. Report errors verbatim and resolve validation or creation failures before further edits. Check the selected vault, paths, and permissions before treating unreadable configuration as missing. Do not assume every CLI failure means the CLI is disabled.

## Reminder fields

Use a configured `circle`: `reference`, `passive`, `inner`, `close`, `orbit`, or `distant`. `reference` means no contact intent; `passive` means no cadence reminders.

The optional fields are:

- `cadence_days_override`: Positive integer replacing the circle cadence.
- `snooze_until`: `YYYY-MM-DD` date; hide until that date. Expired snoozes can be removed.
- `next_action_at`: `YYYY-MM-DD` due date replacing the cadence due date. Keep overdue dates until the action is completed or dismissed; clear the date after logging the intended contact.
- `periodic_contact_reminders`: Defaults to `true`. Set `false` to mute cadence reminders while allowing `next_action_at` to surface the person.
- `contact_channels_ordered_preference`: Ordered list of channel names, such as `[signal, email]`.

Circles configured without cadence stay out of the queue even with `next_action_at` set. See [contact queue](../../docs/DESIGN.md#contact-queue) for scoring.

## Relationship metadata

Use `location`, `relationship_tags`, and `interaction_preferences` for supported
place, category, and contact-mode context. Unknown values stay unknown. An empty
filtered queue may reflect missing metadata or excluded circles; use `fam list`
and relevant notes before concluding no matching people exist. Read and preserve
existing values; do not infer friendship interest from imports or mentions.

## Log a contact

1. Resolve the person note; ask if the name is ambiguous.
2. Establish an actual interaction from the user's report or source evidence. A backlink, dated filename, calendar entry, or suggested outreach alone is insufficient.
3. Resolve the date in the user's time zone. Ask if the date is unknown; do not assume today.
4. Use `fam person log-contact PATH --date YYYY-MM-DD --description "Context"` or MCP `log_contact`. The operation inserts the bullet under the real `## Logged contacts` heading, creates that section if absent, and deduplicates exact date/description retries. Distinguish separate same-day interactions in their descriptions. Add `--complete-action` only if this contact completes the pending action; otherwise its date remains unchanged.

Derive `last_contacted` from this section; never store it in frontmatter. Missing logged history does not prove that no contact occurred.

For scheduled MCP queues, pass the current date in the user's time zone as `on_date`; the server defaults to its own local date.

## Add a person

Check for an existing note anywhere in the vault. If a template is configured, use `fam person ensure "Jane Doe"` (MCP `ensure_person`); otherwise create the note using the [person template](../../examples/person_template.md) in the configured folder or existing layout. Use `fam person update PATH --circle NAME` to set the requested circle while preserving template fields. Log any reported interaction once its date is known.

## Relationship context

Read relevant source notes when preparing outreach or updating relationship state. Put useful context under `## Other references`; do not copy every backlink or add summary placeholders.

FAM does not read or send messages. Use external context only within separate authorization and report unavailable sources. Relationship maintenance alone does not authorize messages, invitations, reactions, or message edits.
