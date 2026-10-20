# fam

Personal CRM in an Obsidian vault. Agents log contacts, suggest follow-ups, and help you review relationships using plain Markdown person notes.

## Usage

Ask your agent to set up [circles and person notes](docs/DESIGN.md#configuration), then log interactions or review whom to contact.

Use one CLI with subcommands (from the repository, prefix these with `uv run`):

```shell
fam today --json
fam list
fam list --sort score --limit 10
fam list --location "San Francisco" --tag friend
fam validate
fam person show "People/@Jane Doe.md"
fam person ensure "Jane Doe"
fam person log-contact "People/@Jane Doe.md" --date 2026-05-01 --description "Lunch"
fam person update "People/@Jane Doe.md" --snooze-until 2026-06-01
fam tend --dry-run
```

See [person operations](docs/DESIGN.md#person-operations) for field removal and
contact logging. Remote agents can use the same operations through the
[optional MCP server](docs/MCP.md), started with `fam mcp`.

Use these skills for CRM work:

- [fam](skills/fam/SKILL.md): person notes, contact logging, cadence, snoozes, and queue commands.
- [fam-review](skills/fam-review/SKILL.md): relationship reviews and next steps.
- [fam-garden](skills/fam-garden/SKILL.md): unattended intake and review preparation.

Keep schedules, source access, tracker paths, and personal exceptions in your task or vault configuration. Gardening saves unresolved decisions for review with you.

## Prerequisites

- Obsidian app installed and running
- Obsidian CLI enabled: **Settings > General > Command line interface**
- Templater plugin for automatic person-note creation
- Python 3.13+ with `uv` (the plugin's scripts run via `uv run`)

## License

MIT.
