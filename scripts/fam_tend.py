"""fam-tend: vault gardener for person notes.

Two passes:

1. **Stub creation** — scan the whole vault for `[[@Name]]` wikilinks with
   no corresponding `@Name.md`. For each, materialize a stub via the
   Templater plugin using paths from `fam-circles.md`
   (`people_folder` + `person_template`).
2. **Backlink fill** — for each person, scan backlinks. Dated meeting-style
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
    the vault. Skips dotfile dirs (`.obsidian`, `.trash`, `.git`, ...).
    """
    found: set[str] = set()
    for md in vault_root.rglob("*.md"):
        rel = md.relative_to(vault_root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        try:
            text = md.read_text(encoding="utf-8")
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


def tend(*, person_name: str | None = None) -> tuple[StubResult, list[TendResult]]:
    vault_root = vault.get_vault_root()
    cfg = config_mod.load(vault_root)
    stubs = _create_missing_stubs(vault_root, cfg) if person_name is None else StubResult()
    targets = [
        p for p in person.discover(vault_root)
        if person_name is None or p.stem.lstrip("@") == person_name
    ]
    results: list[TendResult] = []
    for target_path in targets:
        loaded = person.load(target_path)
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
    return stubs, results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fam-tend")
    parser.add_argument("--person", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true", help="not implemented in MVP; reserved")
    args = parser.parse_args(argv)
    stubs, results = tend(person_name=args.person)
    for name in stubs.created:
        marker = " (retried)" if name in stubs.retried else ""
        print(f"created stub: {name}{marker}")
    for failure in stubs.failed:
        print(f"FAILED stub: {failure}")
    for r in results:
        added = len(r.added_logged) + len(r.added_other)
        if added:
            print(f"{r.person}: +{len(r.added_logged)} logged, +{len(r.added_other)} other")
    if stubs.failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
