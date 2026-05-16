"""fam-tend: vault gardener for person notes.

Three passes:

1. **Stub creation** — scan the whole vault for `[[@Name]]` wikilinks with
   no corresponding `@Name.md`. For each, materialize a stub via the
   Templater plugin using paths from `fam-circles.md`
   (`people_folder` + `person_template`).
2. **People-index sync** — append `- [[@Name]] — contact` lines to
   `<people_folder>/index.md` for any `@*.md` in the folder not already
   wikilinked from the index. Insertion lands after the last existing
   `- [[@*]]` bullet (EOF fallback).
3. **Backlink fill** — for each person, scan backlinks. Dated meeting-style
   notes feed `## Logged contacts`. Other notes feed `## Other references`
   with a TODO placeholder summary the agent fills in later.

Idempotent: re-running does not duplicate bullets and skips stubs that
already exist.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from scripts.lib import config as config_mod
from scripts.lib import person, vault

_DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
_WIKILINK_RE = re.compile(r"\[\[([^\]\n]+)\]\]")
_LOGGED_HEADING = "## Logged contacts"
_OTHER_HEADING = "## Other references"


@dataclass
class TendResult:
    person: str
    added_logged: list[str]
    added_other: list[str]


@dataclass
class StubResult:
    """Outcome of the stub-creation pass."""

    created: list[str] = field(default_factory=list)
    retried: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


@dataclass
class IndexSyncResult:
    """Outcome of the people-folder index-sync pass."""

    added: list[str] = field(default_factory=list)
    skipped_reason: str | None = None


@dataclass
class TendRun:
    """Full outcome of a tend run.

    Iterates as the historical `(stubs, index_sync, results)` tuple so older
    callers that unpack three values continue to work.
    """

    stubs: StubResult
    index_sync: IndexSyncResult
    results: list[TendResult]
    validation_errors: list[str] = field(default_factory=list)

    def __iter__(self):
        yield self.stubs
        yield self.index_sync
        yield self.results


_PERSON_BULLET_RE = re.compile(r"^\s*-\s*\[\[@[^\]|#]+")


def _ensure_trailing_newline(body: str) -> str:
    """Guarantee body ends with `\\n` so splitlines/insert never glues lines.

    `splitlines(keepends=True)` only omits the trailing newline on the LAST
    line, so a heading written without a final `\\n` (common when a fixture
    or hand-edited note ends with `## Other references` and no blank line)
    would later have inserted bullets concatenated onto the same line.
    """
    if body and not body.endswith("\n"):
        return body + "\n"
    return body


def _ensure_section(body: str, heading: str) -> str:
    body = _ensure_trailing_newline(body)
    if heading in body:
        return body
    sep = "\n" if body.endswith("\n") else "\n\n"
    return body + f"{sep}{heading}\n"


def _section_lines(body: str, heading: str) -> tuple[int, int]:
    """Return (start, end) line indices for `heading`'s body content."""
    lines = body.splitlines(keepends=True)
    start = next((i for i, ln in enumerate(lines) if ln.strip() == heading), -1)
    if start == -1:
        return -1, -1
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return start + 1, end


def _wikilink_basename(link: str) -> str:
    """Normalize a wikilink target to its base note name.

    Handles path-prefixed (`wiki/People/index`), aliased (`index|People`),
    and section-anchored (`index#Section`) forms. Strips a trailing `.md`
    extension if present.
    """
    target = link.split("|", 1)[0]
    target = target.split("#", 1)[0]
    target = target.rsplit("/", 1)[-1]
    if target.endswith(".md"):
        target = target[:-3]
    return target


def _existing_link_basenames(body: str) -> set[str]:
    """Return the set of normalized wikilink basenames present anywhere in body.

    Body-wide (not section-scoped) so that a link previously routed into the
    wrong section by an older tend or by hand is still recognized as
    already-present and is not re-added as a duplicate.
    """
    return {_wikilink_basename(m) for m in _WIKILINK_RE.findall(body)}


def _classify(path: Path) -> tuple[bool, date | None]:
    """Return (is_meeting, date) based on filename."""
    m = _DATE_PREFIX_RE.match(path.stem)
    if not m:
        return False, None
    try:
        d = date.fromisoformat(m.group(1))
    except ValueError:
        return False, None
    return True, d


def _scan_at_wikilinks(vault_root: Path) -> set[str]:
    """Return the set of `@`-prefixed wikilink basenames mentioned anywhere in
    the vault. Skips dotfile dirs via `vault.iter_files`.
    """
    found: set[str] = set()
    for md in vault.iter_files(vault_root, "*.md"):
        try:
            text = vault.read_text(md, encoding="utf-8")
        except OSError:
            continue
        for raw in _WIKILINK_RE.findall(text):
            base = _wikilink_basename(raw)
            if base.startswith("@"):
                found.add(base)
    return found


def _create_missing_stubs(vault_root: Path, cfg: config_mod.Config) -> StubResult:
    """First pass: create person stubs for every unresolved `[[@Name]]` link.

    Requires `people_folder` and `person_template` set in `fam-circles.md`
    iff any unresolved links are found. Skips silently when the vault has
    no unresolved links so users without stub-creation needs aren't forced
    to configure these fields.
    """
    existing = {p.stem for p in person.discover(vault_root)}
    mentioned = _scan_at_wikilinks(vault_root)
    unresolved = sorted(mentioned - existing)
    if not unresolved:
        return StubResult()
    if not cfg.people_folder or not cfg.person_template:
        raise config_mod.ConfigError(
            f"unresolved [[@Name]] links found ({len(unresolved)}); set "
            "`people_folder` and `person_template` in fam-circles.md to "
            "enable stub creation, or remove the references."
        )
    template = Path(cfg.person_template)
    folder = Path(cfg.people_folder)
    created: list[str] = []
    retried: list[str] = []
    failed: list[str] = []
    for name in unresolved:
        target = folder / f"{name}.md"
        try:
            attempts = vault.create_from_template(
                template=template, file=target, vault_root=vault_root
            )
            created.append(name)
            if attempts > 1:
                retried.append(name)
        except vault.ObsidianCliError as e:
            failed.append(f"{name}: {e}")
    return StubResult(created=created, retried=retried, failed=failed)


def _sync_people_index(vault_root: Path, cfg: config_mod.Config) -> IndexSyncResult:
    """Append wikilinks for any `@*.md` in `people_folder` missing from `index.md`.

    Insertion lands after the last existing `- [[@*]]` bullet so the new
    entries stay contiguous with the existing person list. EOF fallback when
    no person bullet is present yet.

    Skipped when `people_folder` is unset, or when `<people_folder>/index.md`
    does not exist — the user owns whether the folder has an index at all.
    """
    if not cfg.people_folder:
        return IndexSyncResult(skipped_reason="people_folder unset")
    folder = vault_root / cfg.people_folder
    index_md = folder / "index.md"
    if not index_md.is_file():
        return IndexSyncResult(skipped_reason="index.md missing")
    try:
        text = vault.read_text(index_md, encoding="utf-8")
    except OSError as e:
        return IndexSyncResult(skipped_reason=f"index.md unreadable: {e}")
    existing = _existing_link_basenames(text)
    persons = sorted(p.stem for p in folder.glob("@*.md") if p.is_file())
    missing = [name for name in persons if name not in existing]
    if not missing:
        return IndexSyncResult()
    text = _ensure_trailing_newline(text)
    lines = text.splitlines(keepends=True)
    insert_at = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        if _PERSON_BULLET_RE.match(lines[i]):
            insert_at = i + 1
            break
    new_bullets = [f"- [[{name}]] — contact\n" for name in missing]
    lines[insert_at:insert_at] = new_bullets
    index_md.write_text("".join(lines), encoding="utf-8")
    return IndexSyncResult(added=missing)


def tend(
    *, person_name: str | None = None
) -> TendRun:
    vault_root = vault.get_vault_root()
    cfg = config_mod.load(vault_root)
    stubs = _create_missing_stubs(vault_root, cfg) if person_name is None else StubResult()
    index_sync = (
        _sync_people_index(vault_root, cfg)
        if person_name is None
        else IndexSyncResult(skipped_reason="--person filter set")
    )
    targets = [
        p for p in person.discover(vault_root)
        if person_name is None or p.stem.lstrip("@") == person_name
    ]
    results: list[TendResult] = []
    validation_errors: list[str] = []
    for target_path in targets:
        try:
            loaded = person.load(target_path)
        except person.PersonSchemaError as e:
            validation_errors.append(str(e))
            continue
        except OSError as e:
            validation_errors.append(f"{target_path}: unreadable person note: {e}")
            continue
        body = loaded.body
        body = _ensure_section(body, _LOGGED_HEADING)
        body = _ensure_section(body, _OTHER_HEADING)
        backs = vault.backlinks(target_path.relative_to(vault_root))
        added_logged: list[str] = []
        added_other: list[str] = []
        existing = _existing_link_basenames(body)
        for back in backs:
            link_target = back.stem
            if link_target in existing:
                continue
            is_meeting, d = _classify(back)
            if is_meeting and d is not None:
                _, logged_end = _section_lines(body, _LOGGED_HEADING)
                bullet = f"- {d.isoformat()} — meeting: [[{link_target}]]\n"
                lines = body.splitlines(keepends=True)
                lines.insert(logged_end, bullet)
                body = "".join(lines)
                added_logged.append(link_target)
            else:
                _, other_end = _section_lines(body, _OTHER_HEADING)
                bullet = f"- [[{link_target}]] — TODO: summarize\n"
                lines = body.splitlines(keepends=True)
                lines.insert(other_end, bullet)
                body = "".join(lines)
                added_other.append(link_target)
            existing.add(link_target)
        loaded.body = body
        person.write(loaded)
        results.append(
            TendResult(person=loaded.name, added_logged=added_logged, added_other=added_other)
        )
    return TendRun(
        stubs=stubs,
        index_sync=index_sync,
        results=results,
        validation_errors=validation_errors,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fam-tend")
    parser.add_argument("--person", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true", help="not implemented in MVP; reserved")
    args = parser.parse_args(argv)
    run = tend(person_name=args.person)
    stubs = run.stubs
    index_sync = run.index_sync
    results = run.results
    for name in stubs.created:
        marker = " (retried)" if name in stubs.retried else ""
        print(f"created stub: {name}{marker}")
    for failure in stubs.failed:
        print(f"WARNING: failed stub creation: {failure}", file=sys.stderr)
    for name in index_sync.added:
        print(f"indexed: {name}")
    if index_sync.skipped_reason and index_sync.skipped_reason.startswith("index.md unreadable"):
        print(f"WARNING: skipped people index sync: {index_sync.skipped_reason}", file=sys.stderr)
    for r in results:
        added = len(r.added_logged) + len(r.added_other)
        if added:
            print(f"{r.person}: +{len(r.added_logged)} logged, +{len(r.added_other)} other")
    if run.validation_errors:
        print(
            f"WARNING: skipped {len(run.validation_errors)} invalid person note(s) during fam-tend:",
            file=sys.stderr,
        )
        for err in run.validation_errors:
            print(f"  {err}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
