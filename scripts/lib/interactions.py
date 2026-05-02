"""Parse the `## Logged contacts` section into structured bullets."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from scripts.lib.person import Person


_LOGGED_CONTACTS_HEADING = re.compile(r"^##\s+Logged contacts\s*$", re.MULTILINE)
_NEXT_HEADING = re.compile(r"^##\s+", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*-\s+(\d{4}-\d{2}-\d{2})\s*[—–-]\s*(.*?)\s*$")


@dataclass(frozen=True)
class LoggedContact:
    date: date
    text: str


def _section_body(body: str) -> str | None:
    m = _LOGGED_CONTACTS_HEADING.search(body)
    if not m:
        return None
    start = m.end()
    next_h = _NEXT_HEADING.search(body, pos=start)
    end = next_h.start() if next_h else len(body)
    return body[start:end]


def parse_logged_contacts(body: str) -> list[LoggedContact]:
    section = _section_body(body)
    if section is None:
        return []
    out: list[LoggedContact] = []
    for line in section.splitlines():
        m = _BULLET_RE.match(line)
        if not m:
            continue
        try:
            d = date.fromisoformat(m.group(1))
        except ValueError:
            continue
        out.append(LoggedContact(date=d, text=m.group(2)))
    return out


def last_contacted(person: Person) -> date | None:
    bullets = parse_logged_contacts(person.body)
    return max((b.date for b in bullets), default=None)
