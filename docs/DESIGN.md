# Design and reference

fam stores person notes in an Obsidian vault. One `fam` CLI calculates the
contact queue, validates notes, creates people through Templater, logs contacts,
and updates fam fields. MCP exposes the same shared operations. Agents resolve
identity, assess evidence, and edit free-form relationship context.

## Configuration

`fam-circles.md` contains a fenced `yaml` block. Its `circles` mapping defines
the cadence and alert threshold for each circle you use. Supported names are
`reference`, `passive`, `needs-triage`, `inner`, `close`, `orbit`, and `distant`.

Include `reference`, `passive`, and `needs-triage` with `cadence_days: null` and
`alert_threshold: null`. Use `reference` for people you note without contact
intent, `passive` when there is an explicit choice to keep a relationship
without recurring reminders, and `needs-triage` when contact intent or the
appropriate circle is not yet classified. `needs-triage` is a temporary review
state, not a relationship judgment or contact cadence. Circles with a cadence
need a positive integer `cadence_days` and a finite numeric
`alert_threshold`. To turn off a circle's cadence, set both to `null`.
Every person note must use a configured circle.

Create one `fam-circles.md` anywhere in the vault:

````markdown
```yaml
circles:
  reference: {cadence_days: null, alert_threshold: null}
  passive:   {cadence_days: null, alert_threshold: null}
  needs-triage: {cadence_days: null, alert_threshold: null}
  close:     {cadence_days: 30, alert_threshold: 0.0}
```
````

This defines a 30-day `close` circle. Add other supported circles as needed. A lower threshold includes people earlier; `0.0` includes them on their due date.

Automatic person creation also needs `people_folder` and `person_template`
alongside `circles` in the same YAML block. Both paths are relative to the vault:

```yaml
people_folder: People
person_template: Templates/person_template.md
```

Copy the [person template](../examples/person_template.md) to your template folder. See [creation](#creation) for backend requirements. Use static YAML frontmatter; `processFrontMatter` inside a Templater block can lose fields. The caller sets the destination from `people_folder`; do not move the file in the template.

### Vault selection

By default, fam asks `obsidian vault info=path` for the active vault, then
searches it for one `fam-circles.md`. Discovery excludes hidden directories
and Syncthing conflict copies. Zero or multiple matches are errors.

Set `FAM_VAULT_NAME` to select another registered vault for all `obsidian`
calls. Automation can set `OBSIDIAN_VAULT_PATH` to resolve the root without
calling Obsidian. `FAM_CIRCLES_PATH` selects a specific `fam-circles.md`, using
either an absolute path or a path relative to that root.

When combining a filesystem root override with `FAM_VAULT_NAME`, make sure
both identify the same vault. Each invocation uses one vault.

## Person notes

Person filenames start with `@` and end with `.md`. They can live anywhere
in the vault. Discovery skips hidden directories and Syncthing conflict copies.

Create an `@Name.md` note with a configured circle and contact sections:

```markdown
---
circle: needs-triage
---

## Logged contacts

## Other references
```

See [example person note](../examples/@Jane%20Doe.md) for a filled-out note.
Run `fam validate` after setup.

fam uses these fields and preserves other frontmatter and free-form body
content:

| Field | Meaning |
|-------|---------|
| `circle` | Required configured circle name |
| `cadence_days_override` | Positive integer replacing this person's circle cadence |
| `snooze_until` | `YYYY-MM-DD` date; hide while today is earlier than this date |
| `next_action_at` | `YYYY-MM-DD` date for a one-off action, surfaced separately from cadence reminders |
| `periodic_contact_reminders` | Boolean, default `true`; `false` mutes cadence reminders while explicit one-off actions remain visible |
| `contact_channels_ordered_preference` | List of channel names, such as `[signal, email]`; stored without sending or reading messages |
| `location` | Optional current location string, such as `San Francisco` |
| `relationship_tags` | List of relationship categories, such as `[friend, colleague]` |
| `interaction_preferences` | List of intended modes, such as `[in_person, call]` |
| `important_events` | Named annual or one-off dates with advance notice; see [important events](#important-events) |

The example template starts new people in `needs-triage`. Queue reads never
repair notes. For a missing circle, use
`fam person update "path/to/@Name.md" --circle needs-triage`; this records an
unclassified status without guessing contact intent. This permits only that
target's missing-circle repair; other errors in that note still stop writes.
Unrelated invalid notes do not block a targeted repair.

### Contact history

Log contacts under the exact `## Logged contacts` heading:

```markdown
## Logged contacts
- 2026-05-01 — lunch, discussed weekend plans
```

`last_contacted` is the most recent valid date in this section. fam never stores
it in frontmatter. Other sections, backlinks, and frontmatter dates don't feed
the calculation directly. Stored `last_contacted` frontmatter is rejected;
check the history before removing a stale field. Duplicate real contact sections
and malformed contact bullets fail validation. Contact bullets use `- `, an ISO
date, a dash separator, and a nonempty description; tabs and extra whitespace
around these parts are accepted.

Log a contact only when the user reports it or the agent has evidence of an
actual interaction. A dated note or backlink mentioning someone is not contact
evidence. Scripts never infer contacts from filenames or mentions.

`## Other references` holds context the agent judges useful for the relationship.
There is no automatic copying or summarizing of backlinks.

Keep overdue `next_action_at` dates until you complete or cancel the action.
After logging the intended contact, clear that action date. You can remove
expired snoozes without changing queue behavior.

## Listing people

`fam list` shows all person notes as a table, sorted by name. It includes
inactive circles, snoozed people, and muted reminders. Columns show name,
circle, derived contact date, location, relationship tags, interaction
preferences, and exact vault-relative path. Missing values appear as `-`.

Use `--circle NAME`, `--location TEXT`, `--tag TAG`, and `--interaction VALUE`
to filter people. Location matches a substring, ignoring case; tags and
interaction preferences match whole list entries, ignoring case. Filters
combine as an intersection; missing metadata never matches. `--limit N`
applies after filtering and sorting. `--json` returns person summaries instead
of a table. An empty table explains that no people match; JSON returns `[]`.

`--sort name` is the default. `--sort score` adds a score column and sorts
highest first, then oldest contact date, then name and path. It uses the same
score formula as the contact queue without excluding anyone: snoozed people
and circles without a cadence have score `-inf` and sort last; muted reminders
retain their calculated scores. Never-contacted people with an active cadence
and no action date have score `inf`. JSON uses strings `"inf"` and `"-inf"`.
Use `--on-date YYYY-MM-DD` with `--sort score` to select the scoring date;
the default is the local date. Score sorting validates the vault and configuration
before calculating scores.

`fam list --today` shows the ranked contact queue, one-off actions, triage list,
and important event reminders.
`fam today` is shorthand for the same command, with the same filters and output.
Text output shows separate sections. JSON and MCP `today` return
`{contacts: [...], actions: [...], triage: [...], events: [...]}`. The
`actions` list contains manual `next_action_at` dates for every circle
except `needs-triage`. The `triage` list contains `needs-triage` people, whether or
not they have an action date. Both lists sort by action date then name and
return up to 10 rows by default. The `limit` option caps each list independently.
`fam list` without `--today` still returns a person array.
Queue options `--all` and `--include-snoozed` require this mode. The contact queue
always sorts by score; `--sort name` is not supported with `--today`.

## Contact queue

Circles without a cadence stay out of the recurring contact queue. `fam today`
also excludes snoozed people by default. A `next_action_at` date appears in the
separate one-off `actions` list, so it is never hidden by cadence thresholds.
`next_action_at` temporarily replaces recurring cadence: while set, the person
does not appear in `contacts`, even when the action is in the future. Clearing
the action restores cadence eligibility based on logged contact history.
`needs-triage` appears in the triage list. People with
`periodic_contact_reminders: false` stay out of the recurring contact queue;
their explicit one-off actions remain visible.

For an eligible person without a manual action, the due date is the most recent
logged contact plus the effective cadence. A person with
neither a contact nor a manual action date has an infinite score and comes
first. For everyone else:

```text
days_overdue = (today - due_date).days
score = days_overdue / cadence_days
```

A score of `0` means due today; `1` means one full cadence overdue. For a 30-day cadence, six days overdue gives `0.20` and six days early gives `-0.20`.

The queue includes scores at or above the circle's alert threshold. If nobody
meets their threshold, it returns up to 10 highest-ranked eligible people
below threshold by default; `--limit N` overrides that count.
Each JSON/MCP contact row includes `meets_threshold`: `false` identifies a
fallback or an explicitly requested below-threshold row. Score sign alone
does not establish threshold eligibility.
Snoozes, reminder settings, inactive circles, and requested
filters still apply. It sorts by descending score, then oldest contact date.
Table output includes days
since contact and days overdue. Missing dates appear as `-`.

Queue-specific options:

- `--on-date YYYY-MM-DD`: scoring date; default is the local date.
- `--all`: include below-threshold scores without changing cadence or reminder exclusions.
- `--include-snoozed`: evaluate as if snooze were absent; JSON retains `snoozed: true`.

Filters, limits, and `--json` work as described under [listing people](#listing-people).
An empty queue does not prove no matching person exists; use `fam list` and inspect
notes outside the queue.
JSON contact rows and person summaries include the three metadata fields.
Person summaries also include the normalized `important_events` list.

Empty contact output explains exclusions; JSON uses `contacts: []`.
`--limit 0` returns no rows.

## Important events

Store birthdays, anniversaries, and one-off dates in a person's frontmatter:

```yaml
important_events:
  - name: Birthday
    date: "05-20"
    remind_days_before: 7
  - name: Interview
    date: "2026-11-03"
    remind_days_before: 1
```

Each event requires a nonempty single-line `name` and a valid date. `MM-DD`
repeats annually without needing a birth year; `YYYY-MM-DD` happens once.
`remind_days_before` defaults to 7 and accepts integers from 0 through 366.
Unknown event fields and duplicate identical events fail validation.
Quote annual dates in YAML. Unquoted YAML dates for one-off events also work.
February 29 is observed on February 28 in non-leap years.

```shell
fam events
fam events --on-date 2026-05-15 --days 30 --json
fam person update "People/@Jane Doe.md" --important-events \
    '[{"name":"Birthday","date":"05-20","remind_days_before":7}]'
fam person update "People/@Jane Doe.md" --clear important_events
```

`--important-events` replaces the complete list. Read existing events before
updating so unrelated dates survive; use `[]` or `--clear important_events`
to remove all events. See [field updates](#field-updates) for shared write guarantees.

`fam events` returns each event's next occurrence when its reminder window
has started and the event has not passed. The window includes both the
advance-notice date and event day. `--days N` previews windows starting by
`on_date + N` (default 0); it returns only the next occurrence of each annual
event, even for previews longer than a year. Past one-off events remain stored
but leave the queue; annual events roll forward after event day.

Rows sort by occurrence date, then person name, path, and event name.
JSON returns an array containing `name`, `circle`, `path`, `event`, resolved
`date`, `reminder_at`, `days_until`, and `snoozed`. Empty JSON is `[]`.
`--on-date` defaults to the local date. `--limit N` caps sorted rows.
Snoozed people are hidden unless `--include-snoozed` is set.

Explicit event reminders work in every circle, including `reference` and
`passive`, and when `periodic_contact_reminders` is false. Adding an event is
an explicit reminder choice; it does not change relationship intent or cadence.
Contact logging never completes, shifts, or removes an event reminder and
events never count as contact evidence. Remove a one-off event to cancel it.

`fam today` includes the same current event queue separately from contact
scores, one-off actions, and triage. Metadata and circle filters apply to all
lists; `--limit N` caps each independently. `--all` affects contact scores only.
Events appear even when no contacts are eligible. Reminders are read results,
not delivered notifications or calendar synchronization.

## Person operations

Use [`fam list`](#listing-people) to browse people and filter their metadata.
`fam person show "People/@Jane Doe.md"` returns that summary plus original
Markdown. Use paths returned by the list or queue for reads and writes;
non-person paths, hidden notes, conflict copies, and symlink escapes are rejected.

### Creation

`fam person ensure "Jane Doe"` creates one missing person note from the
configured template, without scanning mentions. Names may include the
leading `@`; paths and wikilink syntax are rejected. An existing note anywhere
in the vault is left unchanged. New notes use `people_folder` and
`person_template`. The default `templater` backend retries and checks that
Templater saved the file; it requires Obsidian running with Templater installed.

For unattended creation, install the
[obsidian-knowledge CLI](https://github.com/crypdick/obsidian-knowledge) and set
`FAM_CREATION_BACKEND=obsidian-knowledge` in the CLI/MCP environment. It passes
the exact configured static person template to `obsidian-knowledge write`
with an explicit vault root and without `--replace`. Existing targets are
refused, and writer errors never trigger another backend. No desktop is needed.
The writer applies its configured, vault-owned creation defaults; provide its
shared `config.yaml` through `XDG_CONFIG_HOME` when the deployment uses those
defaults. FAM does not interpret template code or invent its own metadata.
Templates containing Templater `<%` or `{{` substitution syntax are rejected by
this backend; use the default desktop backend for dynamic templates. Both
template and destination must remain inside the vault. Hidden/protected-source
destinations and case-distinct destination paths are refused.

`fam tend` creates missing person notes from unresolved links. Preview with
`fam tend --dry-run`, then rerun without `--dry-run` if the candidates
are appropriate. The scan finds unresolved `[[@Name]]` links, skipping literal
code examples, path-prefixed links, hidden directories, and conflict copies.
A mention alone does not establish identity, contact, or relationship intent.

Both creation commands accept `--dry-run` and return JSON with `created`,
`retried`, `failed`, and `planned`. A nonempty `failed` list produces a nonzero
exit status, even with partial successes. Tending leaves existing notes and
indexes unchanged and needs no follow-up housekeeping.

Both backends refuse hidden/conflict destinations, paths escaping the vault,
symlinked destination directories, existing targets, and ambiguous case-insensitive
paths. A successful creation
must materialize a regular, discoverable person note with valid frontmatter,
configured circle, and valid contact history. Each desktop CLI call is bounded
to 30 seconds; after errors, fam checks for a materialized note before retrying.
Invalid materialized notes remain on disk and are reported in `failed`;
other valid creations in the batch can still succeed.

### Contact logging

```shell
fam person log-contact "People/@Jane Doe.md" --date 2026-05-01 \
    --description "Lunch, discussed weekend plans" --complete-action
```

The caller must establish an actual interaction and its date. No date is
inferred. Description must be a nonempty single line. Logging appends a bullet
inside the real `## Logged contacts` section, creating the section if missing.
Duplicate real sections or an unclosed code fence preventing insertion fail
without writing. Repeating the same date and description does not add another
bullet; distinguish separate interactions in their descriptions.

`--complete-action` explicitly removes `next_action_at`, including on a retry.
Without it, the pending action stays unchanged. The JSON result includes the
person summary and `added` indicating whether a bullet was added.

### Field updates

```shell
fam person update "People/@Jane Doe.md" --circle close \
    --cadence-days-override 30 --snooze-until 2026-06-01
fam person update "People/@Jane Doe.md" --clear snooze_until --clear next_action_at
```

Supported flags are `--circle`, `--cadence-days-override`, `--snooze-until`,
`--next-action-at`, `--periodic-contact-reminders`,
`--no-periodic-contact-reminders`,
`--contact-channels-ordered-preference signal email`, `--location TEXT`,
`--relationship-tags friend family`, `--interaction-preferences in_person call`,
and `--important-events JSON`.
See [person notes](#person-notes) and [important events](#important-events) for
field types. Populate metadata only from supported context or explicit choices.

Omitted fields stay unchanged. `--clear FIELD` is repeatable and removes an
optional field using its schema name (for example `cadence_days_override`).
Clearing reminder preference restores its default `true`; clearing channel
preferences restores an empty list. Circle is required and cannot be cleared.
Setting and clearing the same field is an error. At least one change is required.

Updates validate proposed values and configured circle before writing. Circle
changes preserve cadence overrides. Writes preserve unrelated frontmatter and
free-form content; YAML formatting can be normalized. Edit free-form context
with file tools; reviews and intake remain agent workflows.

## Validation and failures

`fam validate` checks configuration, every person's frontmatter, and logged
contact bullets. It returns a nonzero exit status for errors.

Mutating scripts use `scripts/lib/validate.py` to validate configuration and
the affected notes before and after writes. Creation validates each materialized
person directly. Explicit circle updates permit the selected note's missing-circle
repair during preflight; its other errors still block the write. Unrelated invalid
notes do not block local updates or creation. Successful mutation does not certify
whole-vault health: use `fam validate` for that check. Queue reads validate and
load the whole population once per invocation, then project all queues from it.
Validation failures name the affected note or configuration field. Failed template creation also
produces a nonzero exit status.

The Obsidian wrapper in `scripts/lib/vault.py` calls the CLI without availability checks and reports failures. Postflight failures leave written files in place; there is no rollback or concurrent-edit protection. Use vault backups for recovery.

fam doesn't integrate messaging channels, watch address books, generate
Obsidian Bases, or deliver notifications. For checks and automation setup, see
[development](development.md).
