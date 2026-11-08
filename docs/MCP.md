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

Tools expose shared FAM operations directly. Names below may have a `fam_`
prefix at the gateway. See [design reference](DESIGN.md) for shared semantics;
MCP-specific arguments and results follow.

### Reads

- `today`: `{contacts: [...], actions: [...], triage: [...], events: [...]}`.
  Optional `on_date`, `include_below_threshold`, `include_snoozed`, `limit`,
  `circle`, `location`, `relationship_tag`, and `interaction_preference`.
  Limits cap each list independently; `include_below_threshold` affects contacts only.
  See [contact queue](DESIGN.md#contact-queue).
- `list_people`: person summaries with exact vault-relative paths. Optional
  `circle`, `location`, `relationship_tag`, `interaction_preference`, `limit`,
  `sort_by` (`name` default or `score`), and `on_date` for scores.
  Includes snoozed people, inactive circles, and muted reminders.
  See [listing people](DESIGN.md#listing-people) for filters and scoring.
- `events`: event reminder array. Optional `on_date`, `days` (preview reminder
  windows, default 0), `include_snoozed`, and `limit`.
  See [important events](DESIGN.md#important-events) for recurrence and row fields.
- `read_person`: original Markdown and summary for required `path`.
- `validate`: `{ok, errors}` for configuration and all person notes; no writes.

Dates default to the server's local date; pass `on_date` for the user's time zone.
Limits and preview days must be nonnegative. Read operations do not repair invalid
notes; use `update_person` for a missing-circle repair.

### Writes

- `ensure_person`: create one missing note for required `person_name`.
  Optional `dry_run` previews without scanning mentions.
- `tend`: bulk creation from unresolved `@` links. Preview with `dry_run: true`.
  Both creation tools return `created`, `retried`, `failed`, and `planned`;
  inspect `failed` even with partial successes. See [creation](DESIGN.md#creation)
  for templates and backend requirements.
- `log_contact`: required `path`, `on_date`, and nonempty single-line
  `description`. Exact date/description retries deduplicate. Optional
  `complete_action: true` clears the pending action; default preserves it.
  Returns person summary and `added`. Caller must establish actual contact and date.
- `update_person`: required `path` plus fields from the
  [person schema](DESIGN.md#person-notes). Omitted/null arguments preserve fields;
  `clear` lists optional schema fields to remove. Cannot clear `circle` or set
  and clear the same field. Returns updated summary. `important_events` replaces
  the whole list: read existing events and preserve unrelated entries.

Use discovered person paths. Tools reject non-person notes, hidden notes,
conflict copies, and paths or symlinks escaping the vault. Writes validate
proposed fields and the vault before and after changes. Postflight failures do
not roll back writes; see [validation and failures](DESIGN.md#validation-and-failures).

Other than default Templater creation, operations need only a configured
filesystem root; headless creation uses the explicit backend above. Use file
tools for free-form context. Reviews, evidence assessment, and external intake
remain agent workflows, not MCP operations.

The dcloud deployment lives in
[dcloud-stacks/fam-mcp](https://github.com/crypdick/dcloud-stacks/tree/main/fam-mcp).
Its existing gateway exposes these tools with the `fam_` prefix.
