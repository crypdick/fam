# Design and reference

fam stores person notes in an Obsidian vault. Scripts calculate the contact
queue and collect backlinks. The agent edits individual notes to log contacts,
change circles, or set reminders.

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

For an initial configuration, create one `fam-circles.md` anywhere in the vault:

````markdown
```yaml
circles:
  reference: {cadence_days: null, alert_threshold: null}
  passive:   {cadence_days: null, alert_threshold: null}
  close:     {cadence_days: 30, alert_threshold: 0.0}
```
````

This defines a 30-day `close` circle. Add `inner`, `orbit`, or `distant` entries
with your own cadence and threshold. A lower threshold includes people earlier.
`0.0` includes them on their due date.

Automatic person creation also needs `people_folder` and `person_template`
alongside `circles` in the same YAML block. Both paths are relative to the vault:

```yaml
people_folder: People
person_template: Templates/person_template.md
```

Copy [person template](../examples/person_template.md) to your template folder
and install Templater. Use static YAML frontmatter in the template.
`processFrontMatter` inside a Templater block can lose fields during creation.
The destination folder comes from `people_folder`.

### Vault selection

By default, fam asks `obsidian vault info=path` for the active vault, then
searches it for one `fam-circles.md`. Discovery excludes hidden directories
and Syncthing conflict copies. Zero or multiple matches are errors.

Set `FAM_VAULT_NAME` to select another registered vault for all `obsidian`
calls. Automation can set `OBSIDIAN_VAULT_PATH` or `OBSIDIAN_VAULT_ROOT` to
resolve the root without calling Obsidian. `OBSIDIAN_VAULT_PATH` takes
precedence. `FAM_CIRCLES_PATH` selects a specific `fam-circles.md`, using
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
Run `/fam-validate` after setup.

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

The example template starts new people in `passive`. `fam-today` repairs
existing notes missing `circle` by writing `circle: reference`.

### Contact history

Log contacts under the exact `## Logged contacts` heading:

```markdown
## Logged contacts
- 2026-05-01 — lunch, discussed weekend plans
```

`last_contacted` is the most recent valid date in this section. fam never stores
it in frontmatter. Other sections, backlinks, and frontmatter dates don't feed
the calculation directly. Malformed contact bullets fail validation.

`## Other references` holds mentions that don't count as contacts. The agent
fills gardener placeholders by reading the linked note and summarizing why
the person appears.

Keep overdue `next_action_at` dates until you complete or cancel the action.
After logging the intended contact, clear that action date. You can remove
expired snoozes without changing queue behavior.

## Contact queue

Circles without a cadence stay out of the queue. `fam-today` also excludes
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

A score of `0` means due today. `1` means one full cadence overdue.
For a 30-day cadence, six days overdue gives `0.20`. Six days before the due
date gives `-0.20`.

The queue includes scores at or above the circle's alert threshold. It sorts
by descending score, then oldest contact date. Table output includes days
since contact and days overdue. Missing dates appear as `-`.

Use these options to change the output:

- `--all` includes scores below the threshold. Circle and reminder exclusions
  still apply.
- `--include-snoozed` evaluates snoozed people as if the snooze were absent.
  Threshold and other exclusions still apply; JSON rows retain `snoozed: true`.
- `--circle NAME` filters to a circle.
- `--limit N` returns at most N rows.
- `--json` returns structured rows. Infinite scores use the string `"inf"`.

## Vault tending

`fam-tend` scans unresolved `[[@Name]]` links and creates stubs through
Templater when you configure a destination and template. It also adds
missing person links to an existing `index.md` in `people_folder`, using
full vault-relative targets.

For each person, the script reads Obsidian backlinks. A source filename
starting with a valid `YYYY-MM-DD` date produces a contact bullet. Other
sources produce reference placeholders:

```markdown
## Logged contacts
- 2026-05-01 — meeting: [[Meetings/2026-05-01 Lunch]]

## Other references
- [[Projects/Climbing trip]] — TODO: summarize
```

Classification uses only the filename, so review dated backlinks that mention
a person without recording contact. New links retain vault-relative paths.
Repeated tending skips existing links with the same full target.

`--person NAME` updates one person's backlinks and skips stub creation and
index updates. `--dry-run` previews stub creation, index updates, and bullets
without creating or editing files. It still reads the vault and requests
backlinks from Obsidian.

## Validation and failures

`fam-validate` checks configuration, every person's frontmatter, and logged
contact bullets. It returns a nonzero exit status for errors.

Mutating scripts use `scripts/lib/validate.py` to validate the whole vault
before and after writes. `fam-today` permits only its missing-circle repair
during preflight. Other invalid notes stop writes. Validation failures name
the affected note or configuration field. Failed stub creation or an unreadable
people index also produces a nonzero exit status.

The Obsidian wrapper in `scripts/lib/vault.py` reports command failures.
It doesn't preflight-check whether the app or command-line tool is available.
Postflight failures leave written files in place. fam has no transaction
rollback or concurrent-edit protection. Use your vault's backup and sync
tools for recovery.

fam doesn't integrate messaging channels, watch address books, generate
Obsidian Bases, or manage birthdays. For checks and automation setup, see
[development](development.md).
