"""Parse the `## Logged contacts` section into structured bullets."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date

from scripts.lib.person import Person

_HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_BULLET_CANDIDATE_RE = re.compile(r"^\s*[-*+](?:\s|$)")
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


def _parse_bullet(line: str) -> LoggedContact | None:
    match = _BULLET_RE.match(line)
    if match and match[2]:
        try:
            return LoggedContact(date=date.fromisoformat(match[1]), text=match[2])
        except ValueError:
            pass
    return None


@dataclass
class _ContactSection:
    start: int
    end: int
    contacts: list[LoggedContact]
    errors: list[str]


def _contact_section(body: str) -> _ContactSection:
    """Scan the one real contact section; ambiguity must never hide history."""
    section = _ContactSection(-1, len(body.splitlines()), [], [])
    inside = False
    for index, line in markdown_lines(body):
        heading = _HEADING_RE.match(line)
        if heading:
            if inside and len(heading[1]) <= 2:
                section.end = index
                inside = False
            if heading[1] == "##" and heading[2] == "Logged contacts":
                if section.start != -1:
                    raise ValueError("multiple Logged contacts sections; resolve before logging")
                section.start = index + 1
                inside = True
            continue
        if inside:
            contact = _parse_bullet(line)
            if contact is not None:
                section.contacts.append(contact)
            elif _BULLET_CANDIDATE_RE.match(line):
                section.errors.append(
                    f"malformed logged contact at body line {index + 1}: {line.strip()}"
                )
    return section


def parse_logged_contacts(body: str) -> list[LoggedContact]:
    return _contact_section(body).contacts


def logged_contact_errors(body: str) -> list[str]:
    try:
        return _contact_section(body).errors
    except ValueError as exc:
        return [str(exc)]


def last_contacted(person: Person) -> date | None:
    bullets = parse_logged_contacts(person.body)
    return max((b.date for b in bullets), default=None)


def append_contact(body: str, on_date: date, description: str) -> str:
    """Append to one real contact section, deduplicating exact date/text retries."""
    if not description.strip() or any(char in description for char in "\r\n\x00"):
        raise ValueError("description must be a nonempty single line")
    description = description.strip()
    section = _contact_section(body)
    if section.errors:
        raise ValueError("\n".join(section.errors))
    contact = LoggedContact(on_date, description)
    if contact in section.contacts:
        return body
    bullet = f"- {on_date.isoformat()} — {description}"
    start, end = section.start, section.end
    if start == -1:
        result = body.rstrip() + "\n\n## Logged contacts\n" + bullet + "\n"
    else:
        lines = body.splitlines()
        # Insert before trailing blank lines so the next section stays separated.
        while end > start and not lines[end - 1].strip():
            end -= 1
        lines.insert(end, bullet)
        result = "\n".join(lines)
    if contact not in parse_logged_contacts(result):
        raise ValueError("cannot append contact inside an unclosed Markdown code fence")
    return result
