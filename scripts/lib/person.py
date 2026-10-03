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
import yaml

from . import vault as vault_mod

CIRCLES = ("reference", "passive", "inner", "close", "orbit", "distant")


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
    periodic_contact_reminders: bool = True
    extra: dict[str, Any] = field(default_factory=dict)


def discover(vault_root: Path) -> list[Path]:
    """All `@*.md` files under vault_root."""
    return sorted(p for p in vault_mod.iter_files(vault_root, "@*.md") if p.is_file())


def _coerce_date(value: Any, file: Path, field_name: str) -> date | None:
    if value is None:
        return None
    if type(value) is date:
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
            if parsed.isoformat() == value:
                return parsed
        except ValueError:
            pass
    raise PersonSchemaError(f"{file}: `{field_name}` must be ISO date, got {value!r}")


def _read_post(path: Path) -> frontmatter.Post:
    try:
        return frontmatter.loads(vault_mod.read_text(path, encoding="utf-8"))
    except yaml.YAMLError as e:
        raise PersonSchemaError(f"{path}: malformed YAML frontmatter: {e}") from e


def load(path: Path, *, default_missing_circle: bool = False) -> Person:
    post = _read_post(path)
    if default_missing_circle and "circle" not in post.metadata:
        post.metadata["circle"] = "reference"
    return _load_post(path, post)


def load_or_set_reference_circle(path: Path) -> Person:
    """Load a person, defaulting missing `circle` frontmatter to `reference`."""
    post = _read_post(path)
    missing_circle = "circle" not in post.metadata
    if missing_circle:
        post.metadata = {"circle": "reference", **post.metadata}
    loaded = _load_post(path, post)
    if missing_circle:
        path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return loaded


def _load_post(path: Path, post: frontmatter.Post) -> Person:
    fm = dict(post.metadata)
    name = path.stem.lstrip("@")
    circle = fm.pop("circle", None)
    if circle is None:
        raise PersonSchemaError(f"{path}: missing required field `circle`")
    if circle not in CIRCLES:
        raise PersonSchemaError(f"{path}: unknown circle {circle!r}; valid: {', '.join(CIRCLES)}")
    cadence_override = fm.pop("cadence_days_override", None)
    if cadence_override is not None:
        if type(cadence_override) is not int or cadence_override <= 0:
            raise PersonSchemaError(f"{path}: `cadence_days_override` must be int > 0")
    snooze = _coerce_date(fm.pop("snooze_until", None), path, "snooze_until")
    next_action = _coerce_date(fm.pop("next_action_at", None), path, "next_action_at")
    channels = fm.pop("contact_channels_ordered_preference", [])
    if not isinstance(channels, list) or not all(isinstance(c, str) for c in channels):
        raise PersonSchemaError(
            f"{path}: `contact_channels_ordered_preference` must be a list of strings"
        )
    pcr_raw = fm.pop("periodic_contact_reminders", True)
    if not isinstance(pcr_raw, bool):
        raise PersonSchemaError(
            f"{path}: `periodic_contact_reminders` must be a boolean, got {pcr_raw!r}"
        )
    # Reject fam-namespace typos: anything starting with `fam_` or matching a
    # known prefix the user might have miswritten.
    for k in fm:
        if not isinstance(k, str):
            raise PersonSchemaError(f"{path}: frontmatter field names must be strings")
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
        periodic_contact_reminders=pcr_raw,
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
    if not person.periodic_contact_reminders:
        fm["periodic_contact_reminders"] = False
    fm.update(person.extra)
    post = frontmatter.Post(person.body, **fm)
    person.path.write_text(frontmatter.dumps(post), encoding="utf-8")
