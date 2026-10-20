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

- `today`: read-only ranked queue with optional `on_date`,
  `include_below_threshold`, `circle`, `include_snoozed`, and nonnegative `limit`.
  Default date uses the server's local timezone. Missing circles fail validation;
  repair explicitly through `update_person`.
- `validate`: `{ok, errors}` for configuration and all person notes; no writes.
- `ensure_person`: required `person_name` selects one note to create if missing.
  Optional `dry_run` previews creation without scanning mentions.
- `tend`: bulk creation from unresolved `@` links; requires `scan: true`.
  Preview with `dry_run: true`. Both creation tools return `created`, `retried`,
  `failed`, and `planned`; inspect `failed` even with partial successes.
- `list_people`: names, circles, derived contact dates, and exact vault-relative
  paths. Optional `circle` filter includes inactive circles too.
- `read_person`: original Markdown and summary for an exact discovered `path`.
- `log_contact`: required `path`, `on_date`, and single-line `description`.
  Exact date/description retries do not duplicate bullets. Optional
  `complete_action: true` clears pending action; default preserves it.
  Returns person summary and `added`.
- `update_person`: required `path` plus fields to set: `circle`,
  `cadence_days_override`, `snooze_until`, `next_action_at`,
  `periodic_contact_reminders`, or `contact_channels_ordered_preference`.
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
