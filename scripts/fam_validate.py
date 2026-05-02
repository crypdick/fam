"""User-runnable wrapper around lib.validate.preflight."""
from __future__ import annotations

import sys

from scripts.lib import validate, vault


def main() -> int:
    vault_root = vault.get_vault_root()
    report = validate.preflight(vault_root)
    if report.ok:
        print("OK")
        return 0
    print("FAIL:")
    for err in report.errors:
        print(f"  {err}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
