---
name: fam
description: Personal CRM. Ranks people due for contact. Reads/writes plain markdown in user's Obsidian vault. Use when user asks "who should I reach out to", "log lunch with X", "snooze Y until next month", or any relationship-maintenance prompt.
---

# fam — Personal CRM

## Prerequisites

- Obsidian app installed + running
- `obsidian` CLI enabled: Settings → General → Command line interface
- (Optional) Templater plugin for `examples/person_template.md`

`obsidian` CLI errors → tell user enable. No preflight check.

## Vault contract

- People = `@<Name>.md` anywhere in vault
- Config = `fam-circles.md` anywhere in vault (unique filename)
- Logged interactions = bullets under `## Logged contacts` heading in person note
- Format: `- YYYY-MM-DD — <freetext>`

## Schema (frontmatter)

Required:
- `circle: passive|inner|close|orbit|distant`

Optional:
- `cadence_days_override: <int>`
- `snooze_until: <ISO date>` — hide until date
- `next_action_at: <ISO date>` — agent-set due override
- `contact_channels_ordered_preference: [imessage, signal, email, ...]`

User's other frontmatter passes through. Don't touch.

## Commands

| Command | Use |
|---------|-----|
| `/fam-today` | Show ranked queue. Default = above-threshold only. `--all` = everyone overdue. `--circle X` = filter. `--json` = structured. |
| `/fam-tend` | Garden vault. Backlinks → `## Logged contacts` (dated) + `## Other references` (TODO summaries to fill). Idempotent. |
| `/fam-validate` | Check config + frontmatter. |

## Logging touches (no script needed)

User says "log a coffee with Christina yesterday, talked about her dog".

1. Find `@Christina*.md` in vault
2. Append under `## Logged contacts`:
   `- 2026-04-30 — coffee, talked about her dog`
3. "yesterday" = today−1; "today" = today; explicit dates → parse as ISO

## Cleanup

`next_action_at` or `snooze_until` in past → clear from frontmatter. Stale overrides accumulate otherwise.

Run before `/fam-today` if frontmatter looks dusty.

## Adding new person

User says "start tracking @Jane Doe, met her at climbing gym, close circle".

1. Create `<vault>/<wherever-people-go>/@Jane Doe.md` (match user's existing layout — check for existing person folder first)
2. Frontmatter: `circle: close` (+ intake info)
3. Body:
   ```
   ## Logged contacts
   - 2026-05-02 — met at climbing gym

   ## Other references
   ```

See `examples/@Jane Doe.md`.

## After tending

`/fam-tend` writes `- [[note]] — TODO: summarize` placeholders under `## Other references`. Fill: read linked note, replace placeholder with one-sentence reason person appears.

Stale or misplaced cruft (TODOs in wrong section, duplicates, drift from older runs)? Fix it. Vault reflects current state. Don't ask.

## Errors

| Error | Fix |
|-------|-----|
| `obsidian: command not found` | Install Obsidian, enable CLI in settings |
| `fam-circles.md not found` | Create one in vault with circles yaml block |
| `multiple fam-circles.md found` | Keep one, delete others |
| `unknown circle <X>` | Wrong circle name in frontmatter |
| `cadence_days_override must be int > 0` | Fix or remove field |

Surface verbatim to user.
