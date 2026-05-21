---
name: fam
description: Personal CRM. Ranks people due for contact. Reads/writes plain markdown in user's Obsidian vault. Use when user asks "who should I reach out to", "log lunch with X", "snooze Y until next month", or any relationship-maintenance prompt.
---

# fam — Personal CRM

## Topic Behavior

When this skill is auto-loaded in a fam-specific chat/topic, treat that topic as the place for using the `fam` skill. Read this `SKILL.md` and use it as the operating guide for the session.

Some deployments route periodic cron output into the same chat/topic. If the user mentions something that needs prior cron context, such as `mark the first one done`, `snooze number 2`, `log that reach-out`, or `who was due today`, inspect the latest relevant cron output before acting. Do not hard-code personal cron job IDs in this public skill; discover the right job/output from the local Hermes cron list or from deployment-local notes.

Then read the newest matching output file and resolve the user's shorthand against that context. Do not guess which person or action they mean from a short chat message alone.


## Prerequisites

- Obsidian app installed + running
- `obsidian` CLI enabled: Settings → General → Command line interface
- Templater plugin (required when `person_template` set in `fam-circles.md`; `/fam-tend` uses it to materialize stubs)

`obsidian` CLI errors → tell user enable. No preflight check.

## Vault contract

- People = `@<Name>.md` anywhere in vault
- Config = `fam-circles.md` anywhere in vault (unique filename)
- Logged interactions = bullets under `## Logged contacts` heading in person note
- Format: `- YYYY-MM-DD — <freetext>`

## Config (`fam-circles.md`)

YAML in fenced ```yaml block. Required: `circles`. Optional (only required when `/fam-tend` finds unresolved `[[@Name]]` links):

- `people_folder: <vault-rel path>` — destination for stubs (e.g. `wiki/People`)
- `person_template: <vault-rel path>` — Templater template (e.g. `Templates/Inputs/person_template.md`). Must use static YAML frontmatter; `processFrontMatter` inside `<%* %>` races Templater's write pipeline and silently loses fields.

## Schema (frontmatter)

Required:
- `circle: reference|passive|inner|close|orbit|distant`
  - `reference` = noted person, no contact intent (dead authors, public figures). Excluded from queue.
  - `passive` = relationship maintained but no cadence. Excluded from queue.

Optional:
- `cadence_days_override: <int>`
- `snooze_until: <ISO date>` — hide until date
- `next_action_at: <ISO date>` — agent-set due override
- `contact_channels_ordered_preference: [imessage, signal, email, ...]`
- `periodic_contact_reminders: false` — mute the cadence-based queue for this person. Still surfaces if `next_action_at` set (for future birthdays / manual nudges). Default `true`. Use when user says "stop nudging me about X" or "no periodic reminders for X" — preferable over flipping them to `passive` since user can keep their circle.

User's other frontmatter passes through. Don't touch.

Design invariant: reference/passive/no-cadence exclusion should flow through the configured circle semantics (`cadence_days: null` / existing queue rules), not through ad-hoc per-command "exclude from alerts" special cases. If a command repairs missing `circle` by setting `reference`, let the reference circle rules do the exclusion.

## Commands

| Command | Use |
|---------|-----|
| `/fam-today` | Show ranked queue. Default = above-threshold only. `--all` = everyone overdue. `--circle X` = filter. `--json` = structured. If a person note is missing `circle`, it silently injects `circle: reference`; normal reference-circle queue rules then apply. |
| `/fam-tend` | Garden vault. (1) Scan whole vault for unresolved `[[@Name]]` links → create person stubs via Templater. (2) Sync `<people_folder>/index.md` with `- [[@Name]] — contact` entries for any persons missing from it. (3) Backlinks → `## Logged contacts` (dated) + `## Other references` (TODO summaries to fill). Idempotent. |
| `/fam-validate` | Check config + frontmatter. |

Repo CLI equivalents exist as console scripts when running from the repo with uv: `uv run fam-tend`, `uv run fam-today`, and `uv run fam-validate`. Prefer these stable entry points over `python scripts/fam_*.py` in automation.

Important: even when executing from the `fam` repo, `fam-circles.md` is **not** expected to live in the repo. The CLI must resolve the Obsidian vault path first, then search for the unique `fam-circles.md` anywhere under that vault. Do not search only under the repo root or the current working directory.

## Cron automation

For recurring fam reminders, use a Hermes pre-run wake gate script under the local Hermes scripts directory (for example `~/.hermes/scripts/<deployment-specific-fam-gate>.py`). Run the repo's stable CLI entry point with an absolute `uv` path and a deployment-local project path, parse the JSON, and emit exactly `{"wakeAgent": false}` when the queue is empty. This skips the LLM and prevents no-op chat alerts like “Nobody is due today.” Only wake the agent for non-empty queues or real failures. In cron subprocesses, remove Hermes' `VIRTUAL_ENV` before calling `uv` to avoid project-venv mismatch warnings. If a deployment has known canonical paths, set `OBSIDIAN_VAULT_PATH` and `FAM_CIRCLES_PATH` in the private cron wrapper or local environment, not in this public skill. This avoids dependency on Obsidian's Electron CLI responsiveness and prevents transient recursive vault-scan failures from masquerading as missing config.

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
| `obsidian: command not found` | Install Obsidian, enable CLI in settings. The repo's vault library may provide platform-specific fallbacks; callers should not need cron-specific PATH injection. |
| `fam-circles.md not found` with Obsidian installer warning text prepended to the path | Older Obsidian CLI prints warnings to stdout before `vault info=path`; `scripts/lib/vault.py` should parse the last absolute-path-looking line. |
| `fam-circles.md not found` | First verify the file actually exists. If it exists but cron/uv reports missing, suspect macOS TCC/Documents permissions for the process running `uv` (or its parent Hermes gateway/launchd service), not missing data. Grant Full Disk Access / Documents access and rerun. |
| `FAM_CIRCLES_PATH points to unreadable fam-circles.md` | macOS TCC/iCloud access failure. Grant Full Disk Access / Documents permission to the cron/uv/Hermes gateway process, then rerun. |
| `multiple fam-circles.md found` | Keep one, delete others |
| `unknown circle <X>` | Wrong circle name in frontmatter |
| `cadence_days_override must be int > 0` | Fix or remove field |
| `OSError: [Errno 11] Resource deadlock avoided` when reading vault notes | macOS/iCloud dataless file. Repo should read through `scripts.lib.vault.read_text()`, which runs `brctl download` then retries. For one-off manual repair: `brctl download '<path>'`. |
| `fam-tend-daily` times out with repeated `failed stub creation` warnings | Inspect unresolved `@` wikilinks with the repo scanner; common causes are incident/changelog examples in backticks, glob placeholders like `[[@*.sync-conflict-*]]`, path-prefixed non-person links like `[[Z/@OpenAI]]`, or org notes mistyped as people. Prefer fixing scanner semantics in the fam repo and correcting the bad link source over raising the global cron script timeout. Verify `unresolved_count 0`, wrapper runtime under 120s, and a manual cron run that records `wakeAgent=false`. |

Surface verbatim to user.
