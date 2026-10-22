# MCP server

Install the optional MCP dependencies and start a local stdio server:

```shell
uv sync --locked --extra mcp
uv run fam mcp
```

Configure an MCP client's command as `uv`, with arguments
`["run", "--project", "/absolute/path/to/fam", "--extra", "mcp", "fam", "mcp"]`.
Set the same vault environment variables used by the CLI. See
[vault selection](DESIGN.md#vault-selection).

For a private HTTP server, put a bearer token in a restricted file:

```shell
uv run --extra mcp fam mcp --transport http --host 0.0.0.0 \
    --token-file /run/secrets/fam-token
```

HTTP requires `--token-file` or `FAM_MCP_TOKEN_FILE`; an absent or empty token
prevents startup. Clients send `Authorization: Bearer <token>` to `/mcp`.
`/healthz` is unauthenticated and checks process liveness only.

## Tools

- `today`: read-only `{contacts: [...], actions: [...], triage: [...], events: [...]}` with optional
  `on_date`,
  `include_below_threshold`, `circle`, `include_snoozed`, nonnegative `limit`,
  `location` (case-insensitive substring), `relationship_tag`, and
  `interaction_preference` (case-insensitive whole-list membership). Filters
  combine before limits. Contact cadence exclusions apply to `contacts`; manual
  `next_action_at` dates for non-triage people appear in `actions`, and
  `needs-triage` people appear in `triage`. Explicit event reminders also work
  in passive/reference circles and with cadence muted.
  Limits apply to each queue independently. The object replaces the former
  contact-only array; consumers must read `contacts` for the previous rows.
  Default date uses the server's local timezone. Missing circles fail validation;
  repair explicitly through `update_person`.
- `events`: read-only event reminder array with optional `on_date`, nonnegative
  `days` (preview reminder windows; default 0), `include_snoozed`, and nonnegative
  `limit`. See [important events](DESIGN.md#important-events) for dates,
  recurrence, window boundaries, and JSON row fields.
- `validate`: `{ok, errors}` for configuration and all person notes; no writes.
- `ensure_person`: required `person_name` selects one note to create if missing.
  Optional `dry_run` previews creation without scanning mentions.
- `tend`: bulk creation from unresolved `@` links.
  Preview with `dry_run: true`. Both creation tools return `created`, `retried`,
  `failed`, and `planned`; inspect `failed` even with partial successes.
- `list_people`: names, circles, derived contact dates, metadata, and exact vault-relative
  paths, sorted by name. Optional `circle`, `location`, `relationship_tag`,
  `interaction_preference`, and nonnegative `limit` use the same filters as
  `fam list`. Includes inactive circles, snoozed people, and muted reminders.
  `sort_by` accepts `name` (default) or `score`; score sorting adds JSON-safe
  scores and accepts `on_date` (default: server-local date). See
  [listing people](DESIGN.md#listing-people) for scoring and tie order.
- `read_person`: original Markdown and summary for an exact discovered `path`.
- `log_contact`: required `path`, `on_date`, and single-line `description`.
  Exact date/description retries do not duplicate bullets. Optional
  `complete_action: true` clears pending action; default preserves it.
  Returns person summary and `added`.
- `update_person`: required `path` plus fields to set: `circle`,
  `cadence_days_override`, `snooze_until`, `next_action_at`,
  `periodic_contact_reminders`, `contact_channels_ordered_preference`,
  `location`, `relationship_tags`, `interaction_preferences`, or `important_events`.
  Event updates replace the complete list; read existing entries first. Each
  event has `name`, `date` (`MM-DD` annual or `YYYY-MM-DD` one-off), and optional
  `remind_days_before` (0–366, default 7).
  Omitted/null arguments preserve fields. `clear` lists optional schema fields
  to remove; setting and clearing the same field fails. Cannot clear circle.
  Returns updated person summary.

Person paths must come from the queue or list. Tools reject non-person notes,
paths outside the vault, hidden notes, conflict copies, and symlink escapes.
Writes validate the vault before and after changes and validate proposed fields
before writing. See [person operations](DESIGN.md#person-operations) for semantics.

Tools call shared Python operations directly, with no shell subprocess for CLI
commands. Templater creation needs Obsidian running; other operations need only
a configured filesystem root. Use existing file tools for free-form relationship
context. Reviews, gardening orchestration, evidence assessment, and external
intake remain agent workflows. See [validation and failures](DESIGN.md#validation-and-failures).

The dcloud deployment lives in
[dcloud-stacks/fam-mcp](https://github.com/crypdick/dcloud-stacks/tree/main/fam-mcp).
Its existing gateway exposes these tools with the `fam_` prefix.
