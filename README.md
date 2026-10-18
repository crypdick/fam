# fam

Personal CRM in an Obsidian vault. Agents log contacts, suggest follow-ups, and help you review relationships using plain Markdown person notes.

## Usage

Ask your agent to set up [circles and person notes](docs/DESIGN.md#configuration), then log interactions or review whom to contact.

Remote agents can use the [MCP server](docs/MCP.md).

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
