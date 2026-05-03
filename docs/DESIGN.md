
# Personal CRM (`fam`) — Design

## Vision

`fam` is the substrate for an agent acting as a relationship coach — proactively nudging maintenance of relationships, surfacing context for upcoming interactions, helping prepare for meetings, learning from interaction history. The MVP described here is the data + queue layer that coach will sit on top of.

## Goals

- Plain-markdown personal CRM stored inside an Obsidian vault.
- Agent-first surface: a Claude Code plugin (skill + helper scripts + slash commands) that abstracts away cross-vault aggregation, otherwise lets the agent edit files directly.
- "Who to reach out to today" ranked queue is the unique value the scripts provide.
- Filing-convention agnostic: `fam` discovers people and contacts from generic backlinks, not hardcoded folder paths. Other users with different vault layouts get the same behavior.

## Future goals (post-MVP)

- Channel integrations (WhatsApp, Signal, iMessage send/read).
- Channel-derived "logged contacts" (parsing message timestamps from external apps and emitting bullets).
- Nextcloud Contacts watcher → intake nudge ("you added Alice to Nextcloud — start tracking?").
- Birthday tracking and reminders.

These are deferred; the design leaves seams (`contact_channels_ordered_preference`, `## Logged contacts` as the canonical write surface) where they will plug in.

## Non-goals

- Bases-file generation for queries inside Obsidian (defer; CLI is enough).
- Concurrency / locking / rollback.
- Backups (rely on the user's vault sync).
- Multi-vault simultaneously (one active vault per invocation).
- TUI / web UI.
- Importing from other CRMs / address books.
- Migrating any one user's pre-existing person-note conventions into the `fam` schema. That is a per-vault chore the user does once.

## Architecture

### Repo layout

```
~/src/PERSONAL/fam/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── fam/
│       └── SKILL.md
├── commands/
│   ├── fam-today.md
│   ├── fam-tend.md
│   └── fam-validate.md
├── scripts/
│   ├── lib/
│   │   ├── vault.py
│   │   ├── config.py
│   │   ├── person.py
│   │   ├── interactions.py
│   │   ├── score.py
│   │   └── validate.py
│   ├── fam-today.py
│   ├── fam-tend.py
│   └── fam-validate.py
├── examples/
│   ├── person_template.md       # reference Templater template
│   └── @Jane Doe.md             # filled-out example person note
├── tests/
│   ├── fixtures/vault/
│   └── test_*.py
├── pyproject.toml
├── README.md
└── CLAUDE.md
```

### Configuration

Single in-vault file: **`fam-circles.md`**. Filename is unique enough that `fam` locates it by glob across the active vault — no environment variables, no out-of-vault config.

Discovery flow:

1. `obsidian vault info=path` → vault root.
2. Glob `<vault_root>/**/fam-circles.md`.
3. Exactly one match → use it. Zero or multiple → abort with actionable error.

The user places `fam-circles.md` wherever fits their vault. A natural location is alongside person notes (e.g. `wiki/People/fam-circles.md`), but any path works.

`fam-circles.md` content — YAML in a fenced code block in the body:

````markdown
# fam — circles

```yaml
circles:
  reference: {cadence_days: null, alert_threshold: null}
  passive:   {cadence_days: null, alert_threshold: null}
  inner:     {cadence_days: 7,    alert_threshold: -0.2}
  close:     {cadence_days: 30,   alert_threshold: 0.0}
  orbit:     {cadence_days: 90,   alert_threshold: 0.2}
  distant:   {cadence_days: 180,  alert_threshold: 0.5}

# Optional: only required when /fam-tend finds unresolved [[@Name]] links
people_folder: wiki/People
person_template: Templates/Inputs/person_template.md
```

`alert_threshold` is the score floor for queue visibility. Lower = surface earlier. `passive` and `reference` excluded entirely.

`passive` = relationship maintained but no cadence. `reference` = noted person, no contact intent (dead authors, public figures, people you've heard of but won't contact).

`people_folder` and `person_template` together let `fam-tend` materialize stubs for unresolved `[[@Name]]` mentions. Both are vault-relative paths. The template must use static YAML frontmatter — `processFrontMatter` inside `<%* %>` blocks races Templater's own write pipeline and silently loses fields.
````

For users with multiple registered Obsidian vaults: pass `FAM_VAULT_NAME=<name>` so `fam`'s `obsidian` CLI calls target the right one. Single-vault users skip this.

### Obsidian CLI: duck-typed

`fam` does not preflight-check that the `obsidian` CLI is installed, enabled, or that the app is running. It just calls. If a call fails, the error propagates verbatim. The `SKILL.md` prerequisites section tells the user how to fix common causes (enable CLI in Settings → General → Command line interface; install Templater).

`lib/vault.py` is a thin wrapper that auto-injects `vault=<name>` (from `FAM_VAULT_NAME` if set; otherwise omitted, falling back to `obsidian`'s active vault).

## Data model

### Person note: `@<Name>.md`

People are identified by an `@` filename prefix anywhere in the vault. `fam` discovers them via `<vault_root>/**/@*.md`. The plugin imposes no `wiki/People/` requirement; users file by their own conventions.

The plugin owns only the `fam`-namespace fields. Users keep any other fields they want.

```yaml
---
# Required
circle: close                       # reference | passive | inner | close | orbit | distant

# Optional
cadence_days_override: 14           # int > 0; overrides circle default
snooze_until: 2026-06-01            # ISO date; hides until then
next_action_at: 2026-05-15          # ISO date; agent-set due override
contact_channels_ordered_preference: [imessage, signal, email]
---

# narrative free body — anything the user wants

## Logged contacts
- 2026-05-01 — quick text re: weekend plans
- 2026-04-22 — lunch at Taco Bell, told me their dog is dying
- 2025-04-21 — meeting: [[2025-04-21 Meeting with Stephen Offer]]

## Other references
- [[Anyscale pricing discussion]] — flagged as primary contact for the EMEA tier
- [[home/dinner-party-guests]] — listed in attendee block
```

- `circle` is the only required field. All others optional with sensible defaults.
- Default circle is `passive` — tracked but never on a cadence. New people start here; user upgrades when they decide to actively maintain. `reference` = no relationship intent (notable but not a contact target).

### `## Logged contacts` — source of truth for contact dates

Bullet format `- YYYY-MM-DD — <freetext>`. Dated bullets are the canonical record of when contact happened. `last_contacted` is `max(date)` over these bullets. No other source feeds it.

Two ways bullets get added:

1. **Agent inline append**, on user prompt. "Log a lunch I had with Foo yesterday at Taco Bell. They told me their dog is dying." → agent appends `- 2026-05-01 — lunch at Taco Bell, dog is dying` under `## Logged contacts`.
2. **Gardener** (`fam-tend`), automatic. Scans the vault for backlinks to each person; for each backlink whose filename or frontmatter implies a date (e.g. `2025-04-21 Meeting with X.md`), adds a `- YYYY-MM-DD — meeting: [[…]]` bullet. Idempotent — re-runs don't duplicate.

### `## Other references` — non-dated mentions

For each backlink to the person whose source note is not a meeting / dated artifact, the gardener adds a bullet `- [[<note>]] — <one-sentence summary>`. The summary is generated by reading the linking file and writing a short TLDR of why the person appears.

`## Other references` is informational only. It does not affect `last_contacted` or score.

## Last-contacted derivation

```python
def last_contacted(person_path) -> date | None:
    return max_date(parse_logged_contacts(person_path))   # or None
```

Pure parse over `## Logged contacts` bullets. No backlink scan, no frontmatter cache. Backlinks feed the gardener, which writes bullets — `fam-today` only reads bullets.

If no dated bullet, `last_contacted` is `None` → score is `+inf` (never-contacted bubbles to top).

## Score model

```python
def score(person, config) -> float:
    circle_cfg = config.circles[person.circle]
    if circle_cfg.cadence_days is None:                      # passive
        return float('-inf')
    if person.snooze_until and today < person.snooze_until:
        return float('-inf')
    cadence = person.cadence_days_override or circle_cfg.cadence_days
    if person.next_action_at:
        anchor = person.next_action_at
    elif person.last_contacted:
        anchor = person.last_contacted + timedelta(days=cadence)
    else:
        return float('+inf')                                 # never contacted
    days_overdue = (today - anchor).days
    return days_overdue / cadence                            # 0 = exactly due, 1 = one cadence overdue
```

Queue filter for `fam-today`:

```python
def in_queue(person, score, config) -> bool:
    if score == float('-inf'):
        return False
    threshold = config.circles[person.circle].alert_threshold
    return score >= threshold
```

Sort: score descending. Tie-break: `last_contacted` ascending (longer ago = higher).

`fam-today --all` skips the threshold filter (still excludes passive/reference + snoozed).

## Command surface

Minimal. Scripts encode only cross-vault aggregation and gardening. Per-person CRUD is direct file editing by agent or human.

### Scripts

| Cmd | Purpose | Output |
|-----|---------|--------|
| `fam-today` | Ranked queue: read every person's `## Logged contacts`, score, sort, threshold-filter | Table (default) or `--json` |
| `fam-tend` | Gardener: (1) scan whole vault for unresolved `[[@Name]]` links → materialize stubs via Templater (`people_folder` + `person_template` config); (2) for each person, scan vault backlinks → write meeting bullets to `## Logged contacts`, summary bullets to `## Other references`. Idempotent. | Per-person change summary + created stubs |
| `fam-validate` | Health check: `fam-circles.md` parses, frontmatter conforms, no orphan refs | Report; exit nonzero on errors |

`fam-today` flags:

- `--all` — include below-threshold (still skips passive + snoozed).
- `--circle <c>` — filter to a circle.
- `--limit N` — top N.
- `--json` — structured output for agent.
- `--include-snoozed` — include snoozed rows; tagged with `snoozed=true` in JSON output.

`fam-today` default output:

```
SCORE  CIRCLE   LAST_CONTACTED  DAYS  DAYS_OVERDUE  PATH
1.18   orbit    2026-01-15      106   16            wiki/People/@Mike Wilby.md
0.92   close    2026-04-04      27    -3            wiki/People/@Christina Zhu.md
0.71   inner    2026-04-25      6     5             wiki/People/@Alejandra Martino.md
```

`DAYS` = days since last contact. `DAYS_OVERDUE` = days past anchor (negative if not yet due). With `--all`, rows with non-positive `DAYS_OVERDUE` may appear.

`fam-tend` flags:

- `--person <name>` — tend a single person; default tends all.
- `--dry-run` — print proposed bullets without writing.

### Slash commands

- `/fam-today [--all] [--circle X]` → `uv run scripts/fam-today.py "$ARGUMENTS"`
- `/fam-tend` → `uv run scripts/fam-tend.py "$ARGUMENTS"`
- `/fam-validate` → `uv run scripts/fam-validate.py`

### Direct vault ops (no script)

| Operation | How |
|-----------|-----|
| Show person | Agent reads `<vault>/**/@<Name>.md` directly |
| Update frontmatter | Agent edits frontmatter directly |
| Add a person | Agent writes a new `@<Name>.md` anywhere appropriate; uses `examples/person_template.md` as a reference if helpful |
| Log a touch | Agent appends a bullet under `## Logged contacts` (`obsidian append` or direct edit) |
| Clear stale `next_action_at` / `snooze_until` | Agent edits frontmatter when the date passes — see `SKILL.md` |

## Validation pipeline

`lib/validate.guard()` is a context manager every mutating script wraps work in.

```python
with validate.guard():
    do_work()
```

- **Preflight**: parse `fam-circles.md`, validate every person's frontmatter against the schema.
- **Postflight**: re-validate touched files.
- **Failure modes**:
  - Preflight fail → abort with actionable error (file path + which check failed).
  - Postflight fail → surface as bug; leave file as-is. No auto-rollback in MVP.

`scripts/fam-validate.py` is a user-runnable wrapper around the same engine.

### Frontmatter checks

- `circle` present, value in known circle set.
- `cadence_days_override`: int > 0 if present.
- `snooze_until`, `next_action_at`: ISO date if present.
- `contact_channels_ordered_preference`: list of strings if present.
- No unknown keys *within the `fam` namespace*. User-namespace keys (anything else) are passed through untouched.

### Config checks

- `fam-circles.md` discoverable (exactly one match in the vault).
- `fam-circles.md` parses; YAML code block extractable.
- Every defined circle has `cadence_days` (`int > 0` or `null`) and `alert_threshold` (`float` or `null`).

## Examples folder

Plugin ships two reference files at `examples/`:

- **`examples/person_template.md`** — a Templater template the user can copy into their own templates folder. Minimal: only the `fam`-namespace fields. User adds their own personal-vault fields if desired.
  ```markdown
  <%*
  await app.fileManager.processFrontMatter(tp.file.find_tfile(tp.file.path(true)), fm => {
    fm["circle"] = "passive";
    fm["contact_channels_ordered_preference"] = [];
  });
  -%>

  ## Logged contacts

  ## Other references
  ```
  No `tp.file.move()` — the user saves the note wherever fits their vault. Filename is `@<Name>.md`.

- **`examples/@Jane Doe.md`** — a filled-out person note demonstrating the schema and section conventions. Used in skill examples and tests.

These are reference material, not loaded at runtime. Plugin code does not depend on their existence.

## SKILL.md

Caveman-terse to save tokens. Covers:

- **Prerequisites**: Obsidian app installed; CLI enabled in Settings → General → Command line interface; Templater plugin installed (only needed if user wants to use the example template).
- **When `obsidian` CLI fails**: tell the user. Don't preflight-check; just propagate.
- **Commands and when to call each**.
- **Schema reference**: `circle`, `cadence_days_override`, `snooze_until`, `next_action_at`, `contact_channels_ordered_preference`. Body sections: `## Logged contacts`, `## Other references`.
- **Cleanup behavior**: when `next_action_at` or `snooze_until` is in the past, clear it. Stale temporary overrides accumulate otherwise.
- **Logging conventions**: `- YYYY-MM-DD — <freetext>` under `## Logged contacts`. Today's date prefix when not specified.
- **Examples** referencing `examples/@Jane Doe.md` and `examples/person_template.md`.

## Testing

### Synthetic vault fixture: `tests/fixtures/vault/`

- Several `@*.md` files at varying paths covering: snoozed, overdue, never-contacted, passive, has `next_action_at`, has `cadence_days_override`.
- `fam-circles.md` at a non-default path (test the discovery glob).
- Various dated and undated notes that link to people — to exercise the gardener.
- Edge cases: malformed frontmatter, unknown circle name, future `snooze_until`, past `next_action_at`, `## Logged contacts` with mixed valid + malformed bullets.
- All names synthetic — no real names.

### Test surface

| Module | Coverage |
|--------|----------|
| `lib/score.py` | Score formula across due, overdue, snoozed, passive, never-contacted, `next_action_at` override, `cadence_days_override` |
| `lib/interactions.py` | `## Logged contacts` parser: well-formed, malformed, empty section, missing section |
| `lib/config.py` | YAML extraction from `fam-circles.md` body; discovery success and failure (zero / multiple matches) |
| `lib/person.py` | Frontmatter read + write + roundtrip, `@`-prefix filename discovery |
| `lib/validate.py` | All failure modes; assertions on error messages |
| `scripts/fam-today.py` | End-to-end on fixture vault: ranking, threshold filter, snooze excluded, JSON output shape, DAYS_OVERDUE column |
| `scripts/fam-tend.py` | Gardener: backlink scan, dated → `## Logged contacts`, undated → `## Other references`, idempotency |

### Mocking

`lib/vault.py` wraps every `obsidian` CLI call. Tests inject canned responses. One integration test optionally hits the real `obsidian` CLI against the fixture vault, gated behind `pytest -m integration`.

### Tooling

`pytest`, `ruff`, `pyright`. Configured in `pyproject.toml`. `uv` for venv.

## Error handling reference

| Failure | Behavior |
|---------|----------|
| `fam-circles.md` not found in vault | Abort with discovery error + suggested filename |
| `fam-circles.md` matched multiple files | Abort; list paths |
| `fam-circles.md` unparseable | Abort with parse error |
| Person frontmatter missing `circle` | Preflight fail; error names file |
| Unknown circle name | Preflight fail; lists valid circles |
| `snooze_until` / `next_action_at` not ISO date | Preflight fail; names file + field |
| `obsidian` CLI returns nonzero | Surface stderr verbatim; SKILL.md tells user to enable the CLI |
| `## Logged contacts` parse: malformed bullet | Skip in derivation; `fam-validate` flags |
| Postflight validation fails | Surface as bug; file left as-is |
| Concurrent edit (file mutated between read+write) | Out of scope MVP |

## Implementation checklist

(For the implementation plan that follows this design.)

1. Repo scaffolding: `.claude-plugin/plugin.json`, `pyproject.toml`, `README.md`, `CLAUDE.md`.
2. `lib/config.py`: `fam-circles.md` discovery + YAML body parser.
3. `lib/vault.py`: `obsidian` CLI wrapper with `vault=` injection.
4. `lib/person.py`: Person dataclass, frontmatter roundtrip, `@`-prefix discovery.
5. `lib/interactions.py`: `## Logged contacts` bullet parser → `last_contacted`.
6. `lib/score.py`: score formula + queue filter.
7. `lib/validate.py`: schema + config validators + `guard()`.
8. `scripts/fam-validate.py`.
9. `scripts/fam-today.py` (with `DAYS_OVERDUE` column).
10. `scripts/fam-tend.py` (gardener — stub creation for unresolved `[[@Name]]` links via Templater, then backlink scan, dated → `## Logged contacts`, undated → `## Other references`, idempotent).
11. `commands/`: slash command frontmatter + bodies.
12. `skills/fam/SKILL.md`: caveman-terse agent contract.
13. `examples/person_template.md` and `examples/@Jane Doe.md`.
14. Test fixtures + tests.
15. Smoke test on the user's real vault.
