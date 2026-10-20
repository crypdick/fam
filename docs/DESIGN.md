# Design and reference

fam stores person notes in an Obsidian vault. One `fam` CLI calculates the
contact queue, validates notes, creates people through Templater, logs contacts,
and updates fam fields. MCP exposes the same shared operations. Agents resolve
identity, assess evidence, and edit free-form relationship context.

## Configuration

`fam-circles.md` contains a fenced `yaml` block. Its `circles` mapping defines
the cadence and alert threshold for each circle you use. Supported names are
`reference`, `passive`, `inner`, `close`, `orbit`, and `distant`.

Include `reference` and `passive` with `cadence_days: null` and
`alert_threshold: null`. Use `reference` for people you note without contact
intent, and `passive` for relationships without reminders. Circles with a
cadence need a positive integer `cadence_days` and a finite numeric
`alert_threshold`. To turn off a circle's cadence, set both to `null`.
Every person note must use a configured circle.

Create one `fam-circles.md` anywhere in the vault:

````markdown
```yaml
circles:
  reference: {cadence_days: null, alert_threshold: null}
  passive:   {cadence_days: null, alert_threshold: null}
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

Copy the [person template](../examples/person_template.md) to your template folder and install Templater. Use static YAML frontmatter; `processFrontMatter` inside a Templater block can lose fields during creation. The caller sets the destination from `people_folder`; do not move the file in the template.

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
circle: close
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
| `next_action_at` | `YYYY-MM-DD` date replacing the cadence-based due date |
| `periodic_contact_reminders` | Boolean, default `true`; `false` mutes cadence reminders unless `next_action_at` is set |
| `contact_channels_ordered_preference` | List of channel names, such as `[signal, email]`; stored without sending or reading messages |
| `location` | Optional current location string, such as `San Francisco` |
| `relationship_tags` | List of relationship categories, such as `[friend, colleague]` |
| `interaction_preferences` | List of intended modes, such as `[in_person, call]` |

The example template starts new people in `passive`. Queue reads never repair
notes. For a missing circle, explicitly run
`fam person update "path/to/@Name.md" --circle reference` (or choose another
configured circle). This permits only that target's missing-circle repair;
other validation errors still stop writes.

### Contact history

Log contacts under the exact `## Logged contacts` heading:

```markdown
## Logged contacts
- 2026-05-01 — lunch, discussed weekend plans
```

`last_contacted` is the most recent valid date in this section. fam never stores
it in frontmatter. Other sections, backlinks, and frontmatter dates don't feed
the calculation directly. Malformed contact bullets fail validation.

Log a contact only when the user reports it or the agent has evidence of an
actual interaction. A dated note or backlink mentioning someone is not contact
evidence. Scripts never infer contacts from filenames or mentions.

`## Other references` holds context the agent judges useful for the relationship.
There is no automatic copying or summarizing of backlinks.

Keep overdue `next_action_at` dates until you complete or cancel the action.
After logging the intended contact, clear that action date. You can remove
expired snoozes without changing queue behavior.

## Contact queue

Circles without a cadence stay out of the queue. `fam today` also excludes
snoozed people by default. People with `periodic_contact_reminders: false`
need a manual action date to appear.

For an eligible person, the due date is `next_action_at` if set. Otherwise it
is the most recent logged contact plus the effective cadence. A person with
neither a contact nor a manual action date has an infinite score and comes
first. For everyone else:

```text
days_overdue = (today - due_date).days
score = days_overdue / cadence_days
```

A score of `0` means due today; `1` means one full cadence overdue. For a 30-day cadence, six days overdue gives `0.20` and six days early gives `-0.20`.

The queue includes scores at or above the circle's alert threshold. It sorts
by descending score, then oldest contact date. Table output includes days
since contact and days overdue. Missing dates appear as `-`.

Use these options to change the output:

- `--on-date YYYY-MM-DD` selects the scoring date; default is the local date.
- `--all` includes scores below the threshold. Circle and reminder exclusions
  still apply.
- `--include-snoozed` evaluates snoozed people as if the snooze were absent.
  Threshold and other exclusions still apply; JSON rows retain `snoozed: true`.
- `--circle NAME` filters to a circle.
- `--location TEXT` matches a location substring, ignoring case.
- `--tag TAG` matches a whole relationship tag, ignoring case.
- `--interaction VALUE` matches a whole interaction preference, ignoring case.
- `--limit N` returns at most N rows.
- `--json` returns structured rows. Infinite scores use the string `"inf"`.

Filters combine as an intersection and apply before `--limit`. Missing metadata
never matches a requested filter. Filtered queues still exclude inactive circles,
muted reminders without action dates, and (unless requested) snoozes, even with
`--all`. An empty queue does not prove that no matching person exists. Use
`fam person list` and inspect notes when reviewing people outside the queue.
JSON queue rows and person summaries include the three metadata fields.

## Person operations

`fam person list [--circle NAME]` returns names, circles, derived contact dates,
and exact vault-relative paths as JSON. It includes inactive circles.
`fam person show "People/@Jane Doe.md"` returns that summary plus original
Markdown. Use paths returned by the list or queue for reads and writes;
non-person paths, hidden notes, conflict copies, and symlink escapes are rejected.

### Creation

`fam person ensure "Jane Doe"` creates one missing person note through the
configured Templater template, without scanning mentions. Names may include the
leading `@`; paths and wikilink syntax are rejected. An existing note anywhere
in the vault is left unchanged. New notes use `people_folder` and
`person_template`. Creation retries and checks that Templater saved the file.

Bulk creation requires `fam tend --scan`. Preview with
`fam tend --scan --dry-run`, then rerun without `--dry-run` if the candidates
are appropriate. The scan finds unresolved `[[@Name]]` links, skipping literal
code examples, path-prefixed links, hidden directories, and conflict copies.
A mention alone does not establish identity, contact, or relationship intent.

Both creation commands accept `--dry-run` and return JSON with `created`,
`retried`, `failed`, and `planned`. A nonempty `failed` list produces a nonzero
exit status, even with partial successes. Tending leaves existing notes and
indexes unchanged and needs no follow-up housekeeping.

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
`--relationship-tags friend family`, and `--interaction-preferences in_person call`.
Location must be a string; tag and preference fields must be lists of strings.
Populate them only from supported context or explicit user choices.
Dates use `YYYY-MM-DD`; cadence must be a positive integer.

Omitted fields stay unchanged. `--clear FIELD` is repeatable and removes an
optional field using its schema name (for example `cadence_days_override`).
Clearing reminder preference restores its default `true`; clearing channel
preferences restores an empty list. Circle is required and cannot be cleared.
Setting and clearing the same field is an error. At least one change is required.

Updates validate proposed values and configured circle before writing. Circle
changes preserve cadence overrides. Both write operations preserve unrelated
frontmatter values and free-form content; YAML formatting can be normalized.
Free-form context edits still use file tools. Relationship reviews, gardening
orchestration, intake connectors, and message sending are not CLI operations.

## Validation and failures

`fam validate` checks configuration, every person's frontmatter, and logged
contact bullets. It returns a nonzero exit status for errors.

Mutating scripts use `scripts/lib/validate.py` to validate the whole vault
before and after writes. Explicit circle updates permit only the selected
note's missing-circle repair during preflight. Other invalid notes stop writes.
Validation failures name the affected note or configuration field. Failed template creation also
produces a nonzero exit status.

The Obsidian wrapper in `scripts/lib/vault.py` calls the CLI without availability checks and reports failures. Postflight failures leave written files in place; there is no rollback or concurrent-edit protection. Use vault backups for recovery.

fam doesn't integrate messaging channels, watch address books, generate
Obsidian Bases, or manage birthdays. For checks and automation setup, see
[development](development.md).
