---
description: Run the fam vault gardener (scan backlinks, update sections)
---

```bash
uv --project ${CLAUDE_PLUGIN_ROOT} run python ${CLAUDE_PLUGIN_ROOT}/scripts/fam_tend.py $ARGUMENTS
```

After tending, look at any `TODO: summarize` lines that were added under
`## Other references` for affected people. For each one, read the linked
note and replace the placeholder with a one-sentence summary explaining
why that person is mentioned.
