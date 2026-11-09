"""Vault reads and configured CLI creation backends.

Duck-typed: do not preflight-check that the CLI is installed or that
the app is running. Just call. If it fails, raise with stderr verbatim
so the caller (or the user) can act on the message.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

MACOS_OBSIDIAN_CLI = Path("/Applications/Obsidian.app/Contents/MacOS/Obsidian")
SYNC_CONFLICT_RE = re.compile(r"\.sync-conflict-\d{8}-\d{6}-[A-Z0-9]+")


class ObsidianCliError(RuntimeError):
    """Raised when a vault CLI operation fails."""


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
    try:
        result = subprocess.run(cmd, capture_output=True, check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ObsidianCliError(f"obsidian call failed: {exc}") from exc
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
    to exactly one match. Return None when absent; reject ambiguous matches.

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
        matches = [child for child in current.iterdir() if child.name.lower() == lower]
        if len(matches) > 1:
            raise ObsidianCliError(f"ambiguous case-distinct path component: {current / part}")
        if not matches:
            return None
        current = matches[0]
    return current


def iter_files(vault_root: Path, pattern: str) -> Iterator[Path]:
    """Yield files matching `pattern` under `vault_root`, skipping non-live files.

    Excludes any path containing a component starting with `.` (e.g.
    `.obsidian/`, `.trash/`, `.stversions/`, `.git/`). Syncthing's
    `.stversions/` mirror in particular will otherwise produce duplicate
    matches of every vault file and break uniqueness contracts.

    Also excludes symlinks resolving outside the vault and Syncthing conflict copies.
    fam operates on canonical live
    notes; treating `@Alice.sync-conflict-...md` as a separate person note makes
    routine gardening rewrite and preserve conflict artifacts instead of letting
    sync-conflict triage delete/merge them.
    """
    resolved_root = vault_root.resolve()
    for p in vault_root.rglob(pattern):
        rel = p.relative_to(vault_root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if any(SYNC_CONFLICT_RE.search(part) for part in rel.parts):
            continue
        if not p.resolve().is_relative_to(resolved_root):
            continue
        yield p


def get_vault_root() -> Path:
    """Return the active vault's filesystem root.

    Prefer explicit environment configuration in automation so scheduled jobs
    do not depend on Obsidian's Electron CLI being responsive. Older Obsidian
    installers can also print advisory text to stdout before the actual path;
    when falling back to the CLI, treat the last absolute-path-looking line as
    the vault root.
    """
    configured = os.environ.get("OBSIDIAN_VAULT_PATH")
    if configured:
        return Path(configured).expanduser()
    out = call(["vault", "info=path"])
    for line in reversed(out.splitlines()):
        text = line.strip()
        if text.startswith("/"):
            return Path(text)
    return Path(out.strip())


def _create_static_from_template(*, template: Path, file: Path, vault_root: Path) -> int:
    """Pass static template bytes to the existing verified, create-only writer."""
    root = vault_root.resolve()
    try:
        content = (root / template).read_bytes()
    except OSError as exc:
        raise ObsidianCliError(f"cannot read configured person template {template}: {exc}") from exc
    if b"<%" in content or b"{{" in content:
        raise ObsidianCliError(
            f"dynamic person template {template} requires the templater creation backend; "
            "obsidian-knowledge accepts only static template content"
        )
    writer = shutil.which("obsidian-knowledge")
    if writer is None:
        raise ObsidianCliError(
            "FAM_CREATION_BACKEND=obsidian-knowledge requires the obsidian-knowledge CLI on PATH"
        )
    try:
        result = subprocess.run(
            [writer, "write", "--vault", str(root), file.as_posix()],
            input=content,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ObsidianCliError(f"obsidian-knowledge create failed: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).decode(errors="replace").strip()
        raise ObsidianCliError(detail or f"obsidian-knowledge exited {result.returncode}")
    if not (root / file).is_file():
        raise ObsidianCliError(
            f"obsidian-knowledge reported success but did not materialize {file}"
        )
    return 1


def create_from_template(
    *,
    template: Path,
    file: Path,
    vault_root: Path,
    max_attempts: int = 3,
    poll_timeout_s: float = 2.0,
    poll_interval_s: float = 0.2,
) -> int:
    """Materialize a configured person template using the selected backend.

    FAM_CREATION_BACKEND=obsidian-knowledge selects the verified writer for
    static templates, including its configured creation metadata. No fallback
    follows writer errors. The default templater backend invokes the desktop.

    Invoke `obsidian templater:create-from-template` to materialize `file`
    from `template`. Both are vault-relative paths; `vault_root` is the
    absolute filesystem root used to verify the file actually persisted.

    Returns the number of attempts used (1 on first-try success).

    The default backend requires Templater and its CLI command. Its template uses
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
    root = vault_root.resolve()
    for relative in (template, file):
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not (root / relative).resolve().is_relative_to(root)
        ):
            raise ObsidianCliError("template and destination must stay inside the selected vault")
    if (
        any(part.startswith(".") or part == "_sources" for part in file.parts)
        or any(SYNC_CONFLICT_RE.search(part) for part in file.parts)
        or not file.name.startswith("@")
        or file.suffix != ".md"
    ):
        raise ObsidianCliError(
            "person destination must be a live @*.md note, not hidden or protected"
        )
    _check_destination_case(file, root)
    abs_target = root / file
    # Discovery does not traverse symlink directories, even within the vault.
    if abs_target.parent.resolve() != abs_target.parent:
        raise ObsidianCliError("person destination cannot traverse symlink directories")
    if abs_target.exists() or abs_target.is_symlink():
        raise ObsidianCliError(f"person destination already exists: {file}")
    backend = os.environ.get("FAM_CREATION_BACKEND", "templater")
    if backend == "obsidian-knowledge":
        return _create_static_from_template(template=template, file=file, vault_root=root)
    if backend != "templater":
        raise ObsidianCliError(
            f"unknown FAM_CREATION_BACKEND {backend!r}; use templater or obsidian-knowledge"
        )
    deadline_steps = max(1, int(poll_timeout_s / poll_interval_s))
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            call(
                [
                    "templater:create-from-template",
                    f"template={template.as_posix()}",
                    f"file={file.as_posix()}",
                ]
            )
        except ObsidianCliError as exc:
            last_err = exc
        # Errors may follow a successful write. Inspect disk before any retry.
        for step in range(deadline_steps + 1):
            _check_destination_case(file, root)
            if not abs_target.resolve().is_relative_to(root):
                raise ObsidianCliError("person destination escaped the selected vault")
            if abs_target.is_file():
                return attempt
            if abs_target.exists():
                raise ObsidianCliError(f"person destination is not a regular file: {file}")
            if step < deadline_steps:
                time.sleep(poll_interval_s)
    raise ObsidianCliError(
        f"templater:create-from-template did not materialize {file} after "
        f"{max_attempts} attempts (last error: {last_err})"
    )


def _check_destination_case(file: Path, root: Path) -> None:
    """Reject collisions even when a later destination component is absent."""
    for depth in range(1, len(file.parts) + 1):
        requested = root.joinpath(*file.parts[:depth])
        actual = resolve_case_insensitive(requested, root)
        if actual is None:
            break
        if actual != requested:
            raise ObsidianCliError(f"case-distinct destination exists: {actual}; requested {file}")
