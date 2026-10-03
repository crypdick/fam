---
description: Run the fam vault gardener (scan backlinks, update sections)
---

```bash
uv --project "${CLAUDE_PLUGIN_ROOT}" run fam-tend $ARGUMENTS
```

For `--dry-run`, present the preview without editing notes, frontmatter,
summaries, or indexes.

After a successful mutating run, fill generated `TODO: summarize`
placeholders in person notes touched by that run. Read the linked note
and write a one-sentence reason under `## Other references`, preserving
the full vault-relative link target.

Cleanup is limited to generated placeholders and exact duplicate
generated bullets in those touched notes. Preserve user-written content.
If ownership is unclear, leave the content and report it.

Surface validation and stub-creation failures before further edits.
