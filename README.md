# fam

Personal CRM stored as plain markdown inside an Obsidian vault. Distributed as a Claude Code plugin: a skill, helper scripts, and slash commands the agent uses to maintain relationships on your behalf.

## Status

Design phase. Implementation has not started.

## Design

Design spec lives in the Obsidian vault, not in this repo:

```
<vault>/wiki/People/plans/2026-05-01-fam-design.md
```

Reasoning: the design closely shapes vault conventions (folder layout, frontmatter schema, Templater template). It belongs alongside the people it describes.

## Vision

The substrate for an agent acting as a relationship coach — proactively nudging maintenance of relationships, surfacing context for upcoming interactions, helping prepare for meetings, learning from interaction history. The MVP is the data + queue layer that coach will sit on top of.

## Layout (planned)

```
.claude-plugin/plugin.json
skills/fam/SKILL.md
commands/
scripts/lib/        # shared Python
scripts/fam-*.py    # entrypoints (uv run)
tests/fixtures/vault/
```

## Requirements

- Obsidian + Obsidian CLI (`obsidian`) installed and configured
- Templater plugin enabled in vault
- Python 3.11+ with `uv`
