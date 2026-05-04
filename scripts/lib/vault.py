"""Thin wrapper around the `obsidian` CLI.

Duck-typed: do not preflight-check that the CLI is installed or that
the app is running. Just call. If it fails, raise with stderr verbatim
so the caller (or the user) can act on the message.
"""
from __future__ import annotations

import os
import subprocess
import time
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
    """Return the active vault's filesystem root.

    Older Obsidian installers can print advisory text to stdout before the
    actual path. Treat the last absolute-path-looking line as the vault root.
    """
    out = call(["vault", "info=path"])
    for line in reversed(out.splitlines()):
        text = line.strip()
        if text.startswith("/"):
            return Path(text)
    return Path(out.strip())


def backlinks(target: Path) -> list[Path]:
    """List vault-relative paths that link to `target`.

    `target` is a vault-relative path (e.g. `People/@Alice.md`).

    The CLI emits human sentences on stdout for non-result conditions
    regardless of `format=` (`"No backlinks found."` for zero results,
    `"Error: File ... not found."` for missing target — both with exit 0).
    Filter to lines that end in `.md` so those sentinels are rejected and
    only real backlink paths survive.
    """
    out = call(["backlinks", f"path={target.as_posix()}", "format=tsv"])
    return [Path(line.strip()) for line in out.splitlines() if line.strip().endswith(".md")]


def create_from_template(
    *,
    template: Path,
    file: Path,
    vault_root: Path,
    max_attempts: int = 3,
    poll_timeout_s: float = 2.0,
    poll_interval_s: float = 0.2,
) -> int:
    """Invoke `obsidian templater:create-from-template` to materialize `file`
    from `template`. Both are vault-relative paths; `vault_root` is the
    absolute filesystem root used to verify the file actually persisted.

    Returns the number of attempts used (1 on first-try success).

    Requires the Templater plugin and its CLI command. The template must use
    static YAML frontmatter — `processFrontMatter` inside `<%* %>` blocks
    races Templater's write pipeline and silently loses fields.

    The CLI returns success even when Templater silently drops the create
    (~10% rate observed under bursts when the new file is also a wikilink
    target elsewhere — link-resolution races the file write). Workaround:
    poll for the file on disk after each call; on timeout, re-issue the
    create up to `max_attempts` times before raising.
    """
    abs_target = vault_root / file
    deadline_steps = max(1, int(poll_timeout_s / poll_interval_s))
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            call([
                "templater:create-from-template",
                f"template={template.as_posix()}",
                f"file={file.as_posix()}",
            ])
        except ObsidianCliError as e:
            last_err = e
            continue
        for _ in range(deadline_steps):
            if abs_target.exists():
                return attempt
            time.sleep(poll_interval_s)
    raise ObsidianCliError(
        f"templater:create-from-template did not materialize {file} after "
        f"{max_attempts} attempts (last error: {last_err})"
    )
