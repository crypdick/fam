---
description: Show ranked queue of people due for contact
---

Run fam-today script, present ranked queue. Pass user flags through as $ARGUMENTS.

```bash
PYTHONPATH=${CLAUDE_PLUGIN_ROOT} uv --project ${CLAUDE_PLUGIN_ROOT} run python ${CLAUDE_PLUGIN_ROOT}/scripts/fam_today.py $ARGUMENTS
```

Script error → surface verbatim. `obsidian` CLI complaint → tell user enable in Obsidian settings: **Settings → General → Command line interface**.
