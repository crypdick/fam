# fam

Personal CRM stored as plain markdown inside an Obsidian vault. Enables agents to help you with relationships: proactively nudging maintenance of relationships, surfacing context for upcoming interactions, helping prepare for meetings, learning from interaction history.

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

For multi-vault setups, set `FAM_VAULT_NAME=<name>` in your environment so `obsidian` CLI calls target the right vault.

## Usage

Tell your agent to set things up :)

## License

MIT.
