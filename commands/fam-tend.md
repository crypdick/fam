---
description: Run the fam vault gardener (scan backlinks, update sections)
---

```bash
PYTHONPATH=${CLAUDE_PLUGIN_ROOT} uv --project ${CLAUDE_PLUGIN_ROOT} run python ${CLAUDE_PLUGIN_ROOT}/scripts/fam_tend.py $ARGUMENTS
```

After tending, fill every `TODO: summarize` line: read linked note,
write one-sentence reason under `## Other references`.

Stale cruft (TODOs in wrong section, duplicates, leftovers from older
runs)? Fix it. Vault reflects current state. Don't ask.
