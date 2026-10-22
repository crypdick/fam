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

Prefer the `fam` CLI. Use available [FAM MCP tools](../../docs/MCP.md#tools) when CLI access is unavailable; tools may have a `fam_` prefix. Use these operations for contact logs and fam fields; use file tools for free-form relationship context.

- `fam list` shows all people as a table, sorted by name, including inactive circles, snoozes, and muted reminders. Use `--circle NAME`, `--location TEXT`, `--tag TAG`, `--interaction VALUE`, `--limit N`, or `--json`. Location uses a case-insensitive substring; tag and mode use whole-list membership. Filters combine before the limit. MCP equivalent: `list_people`.
- `fam today` is shorthand for `fam list --today`: ranked contacts, one-off actions, people needing triage, and event reminders. It accepts the same filters plus `--all`, `--include-snoozed`, and `--on-date YYYY-MM-DD`. JSON returns `{contacts: [...], actions: [...], triage: [...], events: [...]}`; text shows separate sections. Contact filters retain cadence exclusions even with `--all`; event reminders work in every circle. Metadata filters apply to all lists, and `--limit` caps each independently. Missing circles fail validation; set them to `needs-triage` with `fam person update PATH --circle needs-triage` rather than guessing.
- `fam events` shows important event reminders separately. Use `--on-date YYYY-MM-DD`, `--days N` to preview reminder windows, `--limit N`, `--include-snoozed`, and `--json`. MCP equivalent: `events`. See [important events](../../docs/DESIGN.md#important-events) for schema and recurrence.
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
explains the empty contact result; JSON `contacts` remains `[]`. Events can still appear.

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

Use a configured `circle`: `reference`, `passive`, `needs-triage`, `inner`, `close`, `orbit`, or `distant`. `reference` means no contact intent; `passive` means an explicit choice to have no recurring reminders; `needs-triage` is the default until contact intent and circle are clear.

The optional fields are:

- `cadence_days_override`: Positive integer replacing the circle cadence.
- `snooze_until`: `YYYY-MM-DD` date; hide until that date. Expired snoozes can be removed.
- `next_action_at`: `YYYY-MM-DD` one-off action date. It appears in `actions` for every circle except `needs-triage`; triage people appear under `triage` with their action date. Keep overdue dates until the action is completed or dismissed; clear the date after logging the intended contact.
- `periodic_contact_reminders`: Defaults to `true`. Set `false` to mute cadence reminders while allowing `next_action_at` to surface the person.
- `contact_channels_ordered_preference`: Ordered list of channel names, such as `[signal, email]`.

Circles without cadence stay out of the recurring contact queue. Explicit one-off actions remain visible in `actions` regardless of cadence thresholds; `needs-triage` people remain visible in `triage`. See [contact queue](../../docs/DESIGN.md#contact-queue) for scoring.

## Important events

Use `important_events` for supported birthdays, anniversaries, and one-off dates.
Each entry has `name`, `date` (`MM-DD` annual or `YYYY-MM-DD` one-off), and
optional `remind_days_before` (0–366; default 7). February 29 uses February 28
in non-leap years. Capture clearly supported dates proactively; do not ask
permission for the write. Ask only when person identity or date meaning is
materially ambiguous. Record known precision and never invent a birth year.

Read existing events before `fam person update PATH --important-events JSON`
or MCP `update_person` with `important_events`: these replace the full list.
Use `--clear important_events` to remove all. Event reminders respect snoozes,
work without cadence, and remain visible through event day regardless of contact
logging. They never establish contact history. Include relevant event context
in reviews; a reminder does not authorize sending a message.

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

Check for an existing note anywhere in the vault. If a template is configured, use `fam person ensure "Jane Doe"` (MCP `ensure_person`); otherwise create the note using the [person template](../../examples/person_template.md) in the configured folder or existing layout. New or unclassified people default to `needs-triage`; assign a real circle when evidence supports it. Record clear agreed plans, promised follow-ups, and supported important dates directly without asking permission. Assume Ricardo wants to make plans unless he explicitly says he does not and that boundary is recorded in the person note. Never send a message or invitation.

## Relationship context

Read relevant authorized messages when preparing outreach or updating relationship state. Put concise, useful context under `## Other references`, including shared interests, how you met, open plans, and a grounded impression of the person's conversational style. Separate impressions from facts; avoid diagnoses or unsupported sensitive inferences. Do not copy every message or add empty summary placeholders.

When likely duplicate records appear, automatically propose the exact note paths and evidence to Ricardo for confirmation. Do not merge or delete notes before confirmation. After he confirms, add alternate names to the canonical note's `aliases` property and cross-link the other record under `## Other references`; preserve both records unless he explicitly requests a merge. If he rejects the match, record enough disambiguation in FAM to prevent proposing it again.

FAM does not read or send messages. Use external context only within separate authorization and report unavailable sources. Relationship maintenance alone does not authorize messages, invitations, reactions, or message edits.
