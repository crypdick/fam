"""Parse the `## Logged contacts` section into structured bullets."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date

from scripts.lib.person import Person

_HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_BULLET_RE = re.compile(r"^\s*-\s+(\d{4}-\d{2}-\d{2})\s*[—–-]\s*(.*?)\s*$")


@dataclass(frozen=True)
class LoggedContact:
    date: date
    text: str


def markdown_lines(body: str) -> Iterator[tuple[int, str]]:
    """Yield line indices and text outside fenced code blocks."""
    fence = ""
    for index, line in enumerate(body.splitlines()):
        match = _FENCE_RE.match(line)
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence):
                if not match[2].strip():
                    fence = ""
        elif match:
            fence = match[1]
        else:
            yield index, line


def section_lines(body: str, heading: str) -> tuple[int, int]:
    """Return content line bounds for a real Markdown heading, or (-1, -1)."""
    hashes, title = heading.split(" ", 1)
    start = -1
    for index, line in markdown_lines(body):
        match = _HEADING_RE.match(line)
        if not match:
            continue
        if start != -1 and len(match[1]) <= len(hashes):
            return start, index
        if match[1] == hashes and match[2] == title:
            start = index + 1
    return (start, len(body.splitlines())) if start != -1 else (-1, -1)


def _contact_lines(body: str) -> Iterator[tuple[int, str]]:
    start, end = section_lines(body, "## Logged contacts")
    for index, line in markdown_lines(body):
        if start <= index < end:
            yield index, line


def _parse_bullet(line: str) -> LoggedContact | None:
    match = _BULLET_RE.match(line)
    if match:
        try:
            return LoggedContact(date=date.fromisoformat(match[1]), text=match[2])
        except ValueError:
            pass
    return None


def parse_logged_contacts(body: str) -> list[LoggedContact]:
    return [contact for _, line in _contact_lines(body) if (contact := _parse_bullet(line))]


def logged_contact_errors(body: str) -> list[str]:
    return [
        f"malformed logged contact at body line {index + 1}: {line.strip()}"
        for index, line in _contact_lines(body)
        if line.lstrip().startswith("- ") and _parse_bullet(line) is None
    ]


def last_contacted(person: Person) -> date | None:
    bullets = parse_logged_contacts(person.body)
    return max((b.date for b in bullets), default=None)
