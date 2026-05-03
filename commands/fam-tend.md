---
description: Run the fam vault gardener (scan backlinks, update sections)
---

```bash
PYTHONPATH=${CLAUDE_PLUGIN_ROOT} uv --project ${CLAUDE_PLUGIN_ROOT} run python ${CLAUDE_PLUGIN_ROOT}/scripts/fam_tend.py $ARGUMENTS
```

After tending, sweep every `TODO: summarize` line in affected person
notes — including any under `## Logged contacts` left by older tend
runs. For each:

- If `## Other references` already has a summarized line for the same
  wikilink, delete the stale TODO line silently. No need to ask.
- Otherwise read the linked note and replace the placeholder with a
  one-sentence summary under `## Other references`, then delete the
  stale TODO line if it lived elsewhere.
