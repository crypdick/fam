"""fam-tend: vault gardener for person notes.

For each person, scan backlinks. Dated meeting-style notes feed
`## Logged contacts`. Other notes feed `## Other references` with a
TODO placeholder summary the agent fills in later.

Idempotent: re-running does not duplicate bullets.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from scripts.lib import person, vault


_DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
_LOGGED_HEADING = "## Logged contacts"
_OTHER_HEADING = "## Other references"


@dataclass
class TendResult:
    person: str
    added_logged: list[str]
    added_other: list[str]


def _ensure_section(body: str, heading: str) -> str:
    if heading in body:
        return body
    sep = "\n\n" if not body.endswith("\n") else "\n"
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


def _has_link(section_body: str, link_target: str) -> bool:
    return f"[[{link_target}]]" in section_body


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


def tend(*, person_name: str | None = None) -> list[TendResult]:
    vault_root = vault.get_vault_root()
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
        for back in backs:
            link_target = back.stem
            is_meeting, d = _classify(back)
            if is_meeting and d is not None:
                logged_start, logged_end = _section_lines(body, _LOGGED_HEADING)
                section_body = "".join(body.splitlines(keepends=True)[logged_start:logged_end])
                if _has_link(section_body, link_target):
                    continue
                bullet = f"- {d.isoformat()} — meeting: [[{link_target}]]\n"
                lines = body.splitlines(keepends=True)
                lines.insert(logged_end, bullet)
                body = "".join(lines)
                added_logged.append(link_target)
            else:
                other_start, other_end = _section_lines(body, _OTHER_HEADING)
                section_body = "".join(body.splitlines(keepends=True)[other_start:other_end])
                if _has_link(section_body, link_target):
                    continue
                bullet = f"- [[{link_target}]] — TODO: summarize\n"
                lines = body.splitlines(keepends=True)
                lines.insert(other_end, bullet)
                body = "".join(lines)
                added_other.append(link_target)
        loaded.body = body
        person.write(loaded)
        results.append(TendResult(person=loaded.name, added_logged=added_logged, added_other=added_other))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fam-tend")
    parser.add_argument("--person", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true", help="not implemented in MVP; reserved")
    args = parser.parse_args(argv)
    results = tend(person_name=args.person)
    for r in results:
        added = len(r.added_logged) + len(r.added_other)
        if added:
            print(f"{r.person}: +{len(r.added_logged)} logged, +{len(r.added_other)} other")
    return 0


if __name__ == "__main__":
    sys.exit(main())
