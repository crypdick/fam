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

Use the CLI or available [FAM MCP tools](../../docs/MCP.md#tools). MCP tools may have a `fam_` prefix; other person edits use available Obsidian file tools.

- `/fam-today` shows the ranked due queue. Use `--all` for scores below the threshold, `--include-snoozed` for snoozed people, `--circle NAME` to filter, `--limit N` to cap rows, or `--json` for structured output. Missing circles are repaired to `reference`.
- `/fam-tend` creates notes from unresolved `[[@Name]]` links through Templater. `--person "Jane Doe"` ensures one named note exists. Existing notes stay unchanged. `--dry-run` previews without edits. No summaries or index maintenance follow tending.
- `/fam-validate` checks configuration and person notes.

From the repository, use `uv run fam-today`, `uv run fam-tend`, or `uv run fam-validate`. Elsewhere, use `uv --project "PLUGIN_ROOT" run COMMAND`, replacing `PLUGIN_ROOT` with the repository path and `COMMAND` with a command name.

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

## Log a contact

1. Resolve the person note; ask if the name is ambiguous.
2. Establish an actual interaction from the user's report or source evidence. A backlink, dated filename, calendar entry, or suggested outreach alone is insufficient.
3. Resolve the date in the user's time zone. Ask if the date is unknown; do not assume today.
4. Append a bullet under the exact `## Logged contacts` heading, for example: `- 2026-05-01 — coffee, talked about her dog`.

Derive `last_contacted` from this section; never store it in frontmatter. Missing logged history does not prove that no contact occurred.

For scheduled MCP queues, pass the current date in the user's time zone as `on_date`; the server defaults to its own local date.

## Add a person

Check for an existing note anywhere in the vault. If a template is configured, use `fam-tend --person "Jane Doe"`; otherwise create the note using the [person template](../../examples/person_template.md) in the configured folder or existing layout. Set the requested circle while preserving template fields. Log any reported interaction once its date is known.

## Relationship context

Read relevant source notes when preparing outreach or updating relationship state. Put useful context under `## Other references`; do not copy every backlink or add summary placeholders.

FAM does not read or send messages. Use external context only within separate authorization and report unavailable sources. Relationship maintenance alone does not authorize messages, invitations, reactions, or message edits.
