---
description: Validate the fam config and all person notes
---

```bash
PYTHONPATH=${CLAUDE_PLUGIN_ROOT} uv --project ${CLAUDE_PLUGIN_ROOT} run python ${CLAUDE_PLUGIN_ROOT}/scripts/fam_validate.py
```

Surface any error lines. The user can fix in their vault and re-run.
