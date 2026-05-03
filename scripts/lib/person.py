"""Person notes: discovery, frontmatter schema, roundtrip.

A "person" is any markdown file whose basename starts with `@` anywhere
in the vault. Frontmatter has a `fam`-namespace plus arbitrary user
fields, which pass through untouched.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import frontmatter

CIRCLES = ("reference", "passive", "inner", "close", "orbit", "distant")
FAM_FIELDS = (
    "circle",
    "cadence_days_override",
    "snooze_until",
    "next_action_at",
    "contact_channels_ordered_preference",
)


class PersonSchemaError(RuntimeError):
    """Raised when a person note's frontmatter violates the schema."""


@dataclass
class Person:
    path: Path
    name: str
    circle: str
    body: str
    cadence_days_override: int | None = None
    snooze_until: date | None = None
    next_action_at: date | None = None
    contact_channels_ordered_preference: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


def discover(vault_root: Path) -> list[Path]:
    """All `@*.md` files under vault_root."""
    return sorted(p for p in vault_root.rglob("@*.md") if p.is_file())


def _coerce_date(value: Any, file: Path, field_name: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    raise PersonSchemaError(f"{file}: `{field_name}` must be ISO date, got {value!r}")


def load(path: Path) -> Person:
    post = frontmatter.load(str(path))
    fm = dict(post.metadata)
    name = path.stem.lstrip("@")
    circle = fm.pop("circle", None)
    if circle is None:
        raise PersonSchemaError(f"{path}: missing required field `circle`")
    if circle not in CIRCLES:
        raise PersonSchemaError(
            f"{path}: unknown circle {circle!r}; valid: {', '.join(CIRCLES)}"
        )
    cadence_override = fm.pop("cadence_days_override", None)
    if cadence_override is not None:
        if not isinstance(cadence_override, int) or cadence_override <= 0:
            raise PersonSchemaError(f"{path}: `cadence_days_override` must be int > 0")
    snooze = _coerce_date(fm.pop("snooze_until", None), path, "snooze_until")
    next_action = _coerce_date(fm.pop("next_action_at", None), path, "next_action_at")
    channels = fm.pop("contact_channels_ordered_preference", None) or []
    if not isinstance(channels, list) or not all(isinstance(c, str) for c in channels):
        raise PersonSchemaError(
            f"{path}: `contact_channels_ordered_preference` must be a list of strings"
        )
    # Reject fam-namespace typos: anything starting with `fam_` or matching a
    # known prefix the user might have miswritten.
    for k in fm:
        if k.startswith("fam_") or k in {"cadence_days", "snooze", "next_action"}:
            raise PersonSchemaError(f"{path}: unknown fam-namespace field `{k}`")
    return Person(
        path=path,
        name=name,
        circle=circle,
        body=post.content,
        cadence_days_override=cadence_override,
        snooze_until=snooze,
        next_action_at=next_action,
        contact_channels_ordered_preference=channels,
        extra=fm,
    )


def write(person: Person) -> None:
    """Persist person back to disk preserving extra fields."""
    fm: dict[str, Any] = {"circle": person.circle}
    if person.cadence_days_override is not None:
        fm["cadence_days_override"] = person.cadence_days_override
    if person.snooze_until is not None:
        fm["snooze_until"] = person.snooze_until
    if person.next_action_at is not None:
        fm["next_action_at"] = person.next_action_at
    if person.contact_channels_ordered_preference:
        fm["contact_channels_ordered_preference"] = person.contact_channels_ordered_preference
    fm.update(person.extra)
    post = frontmatter.Post(person.body, **fm)
    person.path.write_text(frontmatter.dumps(post), encoding="utf-8")
