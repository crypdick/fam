# fam

Personal CRM stored as plain markdown inside an Obsidian vault. Distributed as a Claude Code plugin: a skill, helper scripts, and slash commands the agent uses to maintain relationships on your behalf.

## Vision

The substrate for an agent acting as a relationship coach — proactively nudging maintenance of relationships, surfacing context for upcoming interactions, helping prepare for meetings, learning from interaction history.

## Install

In Claude Code:

```
/plugin marketplace add crypdick/fam
/plugin install fam@fam
```

## Prerequisites

- Obsidian app installed and running
- Obsidian CLI enabled: **Settings → General → Command line interface**
- (Optional) Templater plugin if you want to use `examples/person_template.md`
- Python 3.13+ with `uv` (the plugin's scripts run via `uv run`)

For multi-vault setups, set `FAM_VAULT_NAME=<name>` in your environment so `obsidian` CLI calls target the right vault. Single-vault users skip this.

## Usage

### One-time setup in your vault

1. Create `fam-circles.md` anywhere in your vault. The unique filename is how `fam` discovers it. Body holds a fenced ```yaml block:

   ```yaml
   circles:
     passive:  {cadence_days: null, alert_threshold: null}
     inner:    {cadence_days: 7,    alert_threshold: -0.2}
     close:    {cadence_days: 30,   alert_threshold: 0.0}
     orbit:    {cadence_days: 90,   alert_threshold: 0.2}
     distant:  {cadence_days: 180,  alert_threshold: 0.5}
   ```

2. For each person you want to track, create or annotate an `@<Name>.md` markdown file (anywhere in the vault) with at least:

   ```yaml
   ---
   circle: passive
   ---

   ## Logged contacts

   ## Other references
   ```

   See `examples/@Jane Doe.md` for a richer reference.

### Day to day

| Slash command | Behavior |
|---------------|----------|
| `/fam-today` | Ranked queue of people due for contact. `--all` to include below-threshold; `--circle <c>` to filter; `--json` for structured. |
| `/fam-tend` | Vault gardener. For each person, scans backlinks; appends dated meeting bullets to `## Logged contacts` and `TODO: summarize` placeholders to `## Other references`. Idempotent. |
| `/fam-validate` | Health check: config sanity, frontmatter conformance. |

The agent can also log interactions directly. Tell Claude "log lunch with Christina yesterday, talked about her dog" — it appends a dated bullet under `## Logged contacts` in the right person note.

## Schema

| Field | Required | Notes |
|-------|----------|-------|
| `circle` | yes | `passive` \| `inner` \| `close` \| `orbit` \| `distant`. New people default to `passive` (tracked, but not on cadence). |
| `cadence_days_override` | no | Per-person override of the circle's cadence. |
| `snooze_until` | no | ISO date. Hides this person from the queue until the date passes. |
| `next_action_at` | no | ISO date. Agent-set due override (can pull in or push out vs the cadence-derived anchor). |
| `contact_channels_ordered_preference` | no | List of channels (`imessage`, `signal`, `email`, …). Future channel-integration skills dispatch in this order. |

User-namespace frontmatter (anything outside the `fam` set above) passes through untouched. Free-form body content (gift ideas, partner names, recurring topics) is whatever you want it to be.

## How `fam` finds things

- **People**: `<vault_root>/**/@*.md` glob.
- **Config**: `<vault_root>/**/fam-circles.md` (must be unique).
- **Meetings / mentions**: `obsidian backlinks` — `fam-tend` walks the vault's backlinks per person and routes them to the right body section.

No hardcoded folder paths. Whatever vault layout you have, `fam` adapts.

## Architecture

See [docs/DESIGN.md](docs/DESIGN.md) for the full spec — schema, score formula, command surface, error handling, and what's deliberately out of scope.

## Develop

```bash
git clone https://github.com/crypdick/fam
cd fam
uv sync --extra dev
uv run pytest        # 53 tests
uv run ruff check .
uv run pyright scripts tests
```

Layout:

```
.claude-plugin/{plugin,marketplace}.json
skills/fam/SKILL.md
commands/{fam-today,fam-tend,fam-validate}.md
scripts/lib/{vault,config,person,interactions,score,validate}.py
scripts/{fam_today,fam_tend,fam_validate}.py
examples/{person_template.md,@Jane Doe.md}
tests/fixtures/vault/   # synthetic
tests/test_*.py
docs/DESIGN.md
```

## License

MIT.
