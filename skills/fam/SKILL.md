---
name: fam
description: Personal CRM. Ranks people due for contact. Reads/writes plain markdown in user's Obsidian vault. Use when user asks "who should I reach out to", "log lunch with X", "snooze Y until next month", or any relationship-maintenance prompt.
---

# fam — Personal CRM

## Prerequisites

- Obsidian app installed + running
- `obsidian` CLI enabled: Settings → General → Command line interface
- (Optional) Templater plugin if user wants `examples/person_template.md`

If `obsidian` CLI errors, tell user to enable. Don't preflight-check.

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
- `snooze_until: <ISO date>` — hides until date
- `next_action_at: <ISO date>` — agent-set due override
- `contact_channels_ordered_preference: [imessage, signal, email, ...]`

User's other frontmatter passes through. Don't touch it.

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
3. Use today minus 1 for "yesterday"; today for "today"; parse explicit dates as ISO

## Cleanup

When `next_action_at` or `snooze_until` is in the past:
- Clear it from frontmatter
- Stale temporary overrides accumulate otherwise

Run before `/fam-today` if frontmatter looks dusty.

## Adding a new person

User says "start tracking @Jane Doe, met her at climbing gym, close circle".

1. Create `<vault>/<wherever-people-go>/@Jane Doe.md` (default `wiki/People/`; check existing layout)
2. Frontmatter: `circle: close` (+ any other intake info)
3. Body:
   ```
   ## Logged contacts
   - 2026-05-02 — met at climbing gym

   ## Other references
   ```

See `examples/@Jane Doe.md`.

## After tending

`/fam-tend` writes `- [[note]] — TODO: summarize` placeholders under `## Other references` for non-meeting backlinks. Agent fills in:

1. Read each linked note
2. Replace `TODO: summarize` with one-sentence reason that person appears

## Errors

| Error | Fix |
|-------|-----|
| `obsidian: command not found` | Install Obsidian, enable CLI in settings |
| `fam-circles.md not found` | Create one in vault with circles yaml block |
| `multiple fam-circles.md found` | Keep one, delete others |
| `unknown circle <X>` | User used wrong circle name in frontmatter |
| `cadence_days_override must be int > 0` | Fix or remove field |

Surface verbatim to user.
