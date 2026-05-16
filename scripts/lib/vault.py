"""Thin wrapper around the `obsidian` CLI.

Duck-typed: do not preflight-check that the CLI is installed or that
the app is running. Just call. If it fails, raise with stderr verbatim
so the caller (or the user) can act on the message.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

MACOS_OBSIDIAN_CLI = Path("/Applications/Obsidian.app/Contents/MacOS/Obsidian")


class ObsidianCliError(RuntimeError):
    """Raised when an `obsidian` invocation returns nonzero."""


def obsidian_executable() -> str:
    """Return an Obsidian CLI executable path.

    Prefer `obsidian` from PATH. On macOS, the app binary also supports the
    CLI but may not be symlinked into non-interactive launchd/cron PATHs.
    """
    found = shutil.which("obsidian")
    if found:
        return found
    if MACOS_OBSIDIAN_CLI.is_file():
        return str(MACOS_OBSIDIAN_CLI)
    return "obsidian"


def call(args: list[str]) -> str:
    """Invoke `obsidian <args>`. Inject vault=<name> from FAM_VAULT_NAME if set.

    Returns stdout decoded as UTF-8. Raises ObsidianCliError on nonzero exit.
    """
    cmd = [obsidian_executable(), *args]
    vault_name = os.environ.get("FAM_VAULT_NAME")
    if vault_name:
        cmd.append(f"vault={vault_name}")
    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace")
        raise ObsidianCliError(stderr.strip() or f"obsidian exited {result.returncode}")
    return result.stdout.decode(errors="replace")


def read_text(path: Path, *, encoding: str = "utf-8") -> str:
    """Read text, materializing iCloud dataless files on macOS if needed."""
    try:
        return path.read_text(encoding=encoding)
    except OSError as e:
        if e.errno != 11 or shutil.which("brctl") is None:
            raise
        subprocess.run(["brctl", "download", str(path)], capture_output=True, check=False)
        return path.read_text(encoding=encoding)


def resolve_case_insensitive(target: Path, vault_root: Path) -> Path | None:
    """Walk `vault_root` toward `target` matching each path component
    case-insensitively. Return the on-disk path if every component resolves
    to exactly one match, else None.

    Used to detect when Obsidian/Templater silently writes a requested file
    at a case-distinct path (e.g. `Wiki/People/` when caller requested
    `wiki/People/`) — typically caused by stale plugin metadata seeding the
    vault's folder index. Triggering that on a case-sensitive filesystem
    produces duplicate stubs because the polled path never appears.
    """
    try:
        rel = target.relative_to(vault_root)
    except ValueError:
        return None
    current = vault_root
    for part in rel.parts:
        if not current.is_dir():
            return None
        lower = part.lower()
        match: Path | None = None
        for child in current.iterdir():
            if child.name.lower() == lower:
                match = child
                break
        if match is None:
            return None
        current = match
    return current


def iter_files(vault_root: Path, pattern: str) -> Iterator[Path]:
    """Yield files matching `pattern` under `vault_root`, skipping dotfile dirs.

    Excludes any path containing a component starting with `.` (e.g.
    `.obsidian/`, `.trash/`, `.stversions/`, `.git/`). Syncthing's
    `.stversions/` mirror in particular will otherwise produce duplicate
    matches of every vault file and break uniqueness contracts.
    """
    for p in vault_root.rglob(pattern):
        rel = p.relative_to(vault_root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        yield p


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

    After each poll-timeout, also check for a case-distinct sibling of the
    requested path (e.g. caller asked for `wiki/People/@X.md`, Templater
    wrote `Wiki/People/@X.md`). On case-sensitive filesystems blindly
    retrying produces duplicate stubs — raise immediately with the actual
    path so the caller can surface the underlying Obsidian misconfiguration.
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
            actual = resolve_case_insensitive(abs_target, vault_root)
            if actual is not None and actual != abs_target:
                raise ObsidianCliError(
                    f"Templater wrote {actual} but {file.as_posix()} was "
                    f"requested (case-distinct path on a case-sensitive "
                    f"filesystem). Aborting before retries duplicate the stub. "
                    f"Likely cause: Obsidian's vault folder index has a "
                    f"case-distinct entry from stale plugin metadata or a "
                    f"prior mobile-peer session. Check .obsidian/ for paths "
                    f"using the wrong case (github-sync-metadata.json, "
                    f"workspace*.json) and remove or repair them."
                )
            if abs_target.exists():
                return attempt
            time.sleep(poll_interval_s)
        actual = resolve_case_insensitive(abs_target, vault_root)
        if actual is not None and actual != abs_target:
            raise ObsidianCliError(
                f"Templater wrote {actual} but {file.as_posix()} was "
                f"requested (case-distinct path on a case-sensitive "
                f"filesystem). Aborting before retries duplicate the stub. "
                f"Likely cause: Obsidian's vault folder index has a "
                f"case-distinct entry from stale plugin metadata or a "
                f"prior mobile-peer session. Check .obsidian/ for paths "
                f"using the wrong case (github-sync-metadata.json, "
                f"workspace*.json) and remove or repair them."
            )
    raise ObsidianCliError(
        f"templater:create-from-template did not materialize {file} after "
        f"{max_attempts} attempts (last error: {last_err})"
    )
