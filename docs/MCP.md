# MCP server

Install the optional MCP dependencies and start a local stdio server:

```sh
uv sync --locked --extra mcp
uv run fam-mcp
```

Configure an MCP client's command as `uv`, with arguments
`["run", "--project", "/absolute/path/to/fam", "--extra", "mcp", "fam-mcp"]`.
Set the same vault environment variables used by the CLI. See
[vault selection](DESIGN.md#vault-selection).

For a private HTTP server, put a bearer token in a restricted file:

```sh
uv run --extra mcp fam-mcp --transport http --host 0.0.0.0 --token-file /run/secrets/fam-token
```

HTTP requires `--token-file` or `FAM_MCP_TOKEN_FILE`; an absent or empty token
prevents startup. Clients send `Authorization: Bearer <token>` to `/mcp`.
`/healthz` is unauthenticated and checks process liveness only.

## Tools

- `today`: ranked queue with optional `on_date`, `include_below_threshold`,
  `circle`, `include_snoozed`, and nonnegative `limit`. Default date uses the
  server's local timezone. Repairs missing circles to `reference`, as the CLI
  does; this tool is advertised as mutating.
- `validate`: `{ok, errors}` for the configuration and all person notes.
  Invalid notes are reported without writing files.
- `tend`: `person_name` selects one person; otherwise scans unresolved `@`
  links. `dry_run` previews creation. Returns `created`, `retried`, `failed`,
  and `planned`; inspect `failed` even when other notes were created.
- `list_people`: names, circles, contact dates, and exact vault-relative paths.
  Optional `circle` filter includes inactive circles too.
- `read_person`: original Markdown and derived contact date for an exact person
  `path` returned by the queue or list. Rejects non-person notes and paths outside
  the vault. Discovery excludes hidden files, conflict copies, and symlink escapes.

Tools reuse the CLI's scoring, validation, and Templater creation. Tending needs
Obsidian and Templater running; queue and reads need only a configured filesystem
root. Other person edits use existing Obsidian file tools. Contact history is
never inferred from mentions or dated filenames.

MCP does not add transactions or concurrent-edit protection. Existing preflight
and postflight validation applies to mutations. See [failure behavior](DESIGN.md#validation-and-failures).

The dcloud deployment lives in
[dcloud-stacks/fam-mcp](https://github.com/crypdick/dcloud-stacks/tree/main/fam-mcp).
Its existing gateway exposes these tools with the `fam_` prefix.
