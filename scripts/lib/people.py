"""Person operations shared by CLI and MCP."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

from . import config, interactions, person, score, validate, vault

EDITABLE_FIELDS = (
    "circle",
    "cadence_days_override",
    "snooze_until",
    "next_action_at",
    "periodic_contact_reminders",
    "contact_channels_ordered_preference",
    "location",
    "relationship_tags",
    "interaction_preferences",
    "important_events",
)
OPTIONAL_FIELDS = EDITABLE_FIELDS[1:]


def resolve_path(root: Path, path: str) -> Path:
    """Require an exact, discovered vault-relative person path."""
    relative = Path(path)
    target = root / relative
    if relative.is_absolute() or ".." in relative.parts or target not in person.discover(root):
        raise ValueError("path must identify a discovered person note inside the vault")
    return target


def _summary(loaded: person.Person, root: Path) -> dict[str, Any]:
    last = interactions.last_contacted(loaded)
    return {
        "name": loaded.name,
        "circle": loaded.circle,
        "path": str(loaded.path.relative_to(root)),
        "last_contacted": last.isoformat() if last else None,
        "location": loaded.location,
        "relationship_tags": loaded.relationship_tags,
        "interaction_preferences": loaded.interaction_preferences,
        "important_events": loaded.important_events,
    }


def matching_people(
    root: Path,
    *,
    circle: str | None = None,
    location: str | None = None,
    relationship_tag: str | None = None,
    interaction_preference: str | None = None,
) -> list[person.Person]:
    """Filter discovered people without applying contact-queue exclusions."""
    if circle is not None and circle not in person.CIRCLES:
        raise ValueError("unknown circle")
    matches = []
    for path in person.discover(root):
        p = person.load(path)
        if circle is not None and p.circle != circle:
            continue
        if location is not None and (
            p.location is None or location.casefold() not in p.location.casefold()
        ):
            continue
        if relationship_tag is not None and relationship_tag.casefold() not in {
            tag.casefold() for tag in p.relationship_tags
        }:
            continue
        if interaction_preference is not None and interaction_preference.casefold() not in {
            preference.casefold() for preference in p.interaction_preferences
        }:
            continue
        matches.append(p)
    return matches


def list_people(
    circle: str | None = None,
    *,
    location: str | None = None,
    relationship_tag: str | None = None,
    interaction_preference: str | None = None,
    limit: int | None = None,
    sort_by: str = "name",
    on_date: date | None = None,
) -> list[dict[str, Any]]:
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError("limit must be a nonnegative integer")
    if sort_by not in {"name", "score"}:
        raise ValueError("sort_by must be name or score")
    if on_date is not None and sort_by != "score":
        raise ValueError("on_date requires sorting by score")
    root = vault.get_vault_root()
    cfg = None
    if sort_by == "score":
        report = validate.preflight(root)
        if not report.ok:
            raise validate.ValidationError("preflight failed:\n  " + "\n  ".join(report.errors))
        cfg = config.load(root)
    loaded = matching_people(
        root,
        circle=circle,
        location=location,
        relationship_tag=relationship_tag,
        interaction_preference=interaction_preference,
    )
    loaded.sort(key=lambda p: (p.name.casefold(), str(p.path)))
    rows = [_summary(p, root) for p in loaded]
    if cfg is not None:
        today = on_date or date.today()
        for p, row in zip(loaded, rows, strict=True):
            row["score"] = score.score(
                p, last=interactions.last_contacted(p), today=today, config=cfg
            )
        rows.sort(key=lambda row: (-row["score"], row["last_contacted"] or ""))
        for row in rows:
            if math.isinf(row["score"]):
                row["score"] = str(row["score"])
    if limit is not None:
        rows = rows[:limit]
    return rows


def read_person(path: str) -> dict[str, Any]:
    root = vault.get_vault_root()
    target = resolve_path(root, path)
    return {**_summary(person.load(target), root), "content": vault.read_text(target)}


def update_person(
    path: str, changes: dict[str, Any], clear: Sequence[str] | None = None
) -> dict[str, Any]:
    clear = clear or []
    if not changes and not clear:
        raise ValueError("provide at least one field to update or clear")
    if any(key not in EDITABLE_FIELDS for key in changes):
        raise ValueError("changes may contain only fam person fields")
    if any(key not in OPTIONAL_FIELDS for key in clear):
        raise ValueError("only optional fam person fields may be cleared")
    if set(changes) & set(clear):
        raise ValueError("cannot both set and clear the same field")
    if any(value is None for value in changes.values()):
        raise ValueError("use clear to remove fields; changes must not contain null")
    root = vault.get_vault_root()
    target = resolve_path(root, path)
    # Only this target's missing circle may be repaired; all other errors block writes.
    repair = target if "circle" in changes else None
    loaded = person.with_updates(target, {**changes, **dict.fromkeys(clear)})
    cfg = config.load(root)
    if loaded.circle not in cfg.circles:
        raise ValueError(f"circle {loaded.circle!r} is not configured in {cfg.path}")
    with validate.guard(root, allow_missing_circle=repair):
        person.write(loaded)
    return _summary(loaded, root)


def log_contact(
    path: str, on_date: date, description: str, *, complete_action: bool = False
) -> dict[str, Any]:
    if type(on_date) is not date:
        raise ValueError("contact date must be an explicit date")
    if not description.strip() or any(char in description for char in "\r\n\x00"):
        raise ValueError("description must be a nonempty single line")
    description = description.strip()
    root = vault.get_vault_root()
    target = resolve_path(root, path)
    with validate.guard(root):
        loaded = person.load(target)
        body = interactions.append_contact(loaded.body, on_date, description)
        added = body != loaded.body
        if added or (complete_action and loaded.next_action_at is not None):
            loaded.body = body
            if complete_action:
                loaded.next_action_at = None
            person.write(loaded)
    return {**_summary(loaded, root), "added": added}
