"""Thin wrapper around the `obsidian` CLI.

Duck-typed: do not preflight-check that the CLI is installed or that
the app is running. Just call. If it fails, raise with stderr verbatim
so the caller (or the user) can act on the message.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


class ObsidianCliError(RuntimeError):
    """Raised when an `obsidian` invocation returns nonzero."""


def call(args: list[str]) -> str:
    """Invoke `obsidian <args>`. Inject vault=<name> from FAM_VAULT_NAME if set.

    Returns stdout decoded as UTF-8. Raises ObsidianCliError on nonzero exit.
    """
    cmd = ["obsidian", *args]
    vault_name = os.environ.get("FAM_VAULT_NAME")
    if vault_name:
        cmd.append(f"vault={vault_name}")
    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace")
        raise ObsidianCliError(stderr.strip() or f"obsidian exited {result.returncode}")
    return result.stdout.decode(errors="replace")


def get_vault_root() -> Path:
    """Return the active vault's filesystem root."""
    return Path(call(["vault", "info=path"]).strip())


def backlinks(target: Path) -> list[Path]:
    """List vault-relative paths that link to `target`.

    `target` is a vault-relative path (e.g. `People/@Alice.md`).
    """
    out = call(["backlinks", f"path={target.as_posix()}", "format=tsv"])
    return [Path(line) for line in out.splitlines() if line.strip()]
