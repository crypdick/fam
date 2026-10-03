"""User-runnable wrapper around lib.validate.preflight."""

from __future__ import annotations

import argparse
import sys

from scripts.lib import validate, vault


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(prog="fam-validate").parse_args(argv)
    try:
        vault_root = vault.get_vault_root()
        report = validate.preflight(vault_root)
    except (vault.ObsidianCliError, OSError) as e:
        print(str(e), file=sys.stderr)
        return 1
    if report.ok:
        print("OK")
        return 0
    print("FAIL:")
    for err in report.errors:
        print(f"  {err}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
