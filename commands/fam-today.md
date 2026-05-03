---
description: Show ranked queue of people due for contact
---

Run the fam-today script and present the ranked queue. Pass through any flags
the user supplied as $ARGUMENTS.

```bash
PYTHONPATH=${CLAUDE_PLUGIN_ROOT} uv --project ${CLAUDE_PLUGIN_ROOT} run python ${CLAUDE_PLUGIN_ROOT}/scripts/fam_today.py $ARGUMENTS
```

If the script errors, surface the error message verbatim. If it complains
about the `obsidian` CLI, tell the user to enable it in Obsidian settings:
**Settings → General → Command line interface**.
