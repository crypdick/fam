# fam

Personal CRM stored as plain markdown inside an Obsidian vault. Enables agents to help you with relationships: proactively nudging maintenance of relationships, surfacing context for upcoming interactions, helping prepare for meetings, learning from interaction history.

## Usage

Tell your agent to set things up :)

Remote agents can use the [MCP server](docs/MCP.md).

Skills separate direct note operations from relationship reviews and background work:

- [fam](skills/fam/SKILL.md): person notes, contact logging, cadence, snoozes, and queue commands.
- [fam-review](skills/fam-review/SKILL.md): an interactive review that turns your relationship choices into next steps and reminders.
- [fam-garden](skills/fam-garden/SKILL.md): unattended intake and review preparation using configured sources and saved state.

Schedules, source access, tracker paths, and personal exceptions stay in your task
or vault configuration. Gardening saves unresolved decisions for a review with you.

## Prerequisites

- Obsidian app installed and running
- Obsidian CLI enabled: **Settings → General → Command line interface**
- (Optional) Templater plugin if you want to use `examples/person_template.md`
- Python 3.13+ with `uv` (the plugin's scripts run via `uv run`)

## License

MIT.
