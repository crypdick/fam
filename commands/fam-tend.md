---
description: Create missing person notes through Templater
---

```bash
uv --project "${CLAUDE_PLUGIN_ROOT}" run fam-tend $ARGUMENTS
```

`--person "Name"` ensures one named note exists; default scans unresolved
`[[@Name]]` links. Existing notes stay unchanged. No summaries or index
maintenance needed after running.

For `--dry-run`, present the preview without editing files.
Surface validation and template-creation failures before further edits.
