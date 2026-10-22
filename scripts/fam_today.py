"""Daily FAM queues for cadence contacts, one-off actions, triage, and events."""

from __future__ import annotations

import json as _json
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

from scripts import fam_events
from scripts.lib import config as config_mod
from scripts.lib import interactions, people, person, score, validate, vault


@dataclass(frozen=True)
class Row:
    name: str
    circle: str
    last_contacted: date | None
    days: int | None
    days_overdue: int | None
    score: float
    path: Path
    snoozed: bool
    location: str | None
    relationship_tags: list[str]
    interaction_preferences: list[str]


@dataclass(frozen=True)
class OneShotRow:
    name: str
    circle: str
    next_action_at: date | None
    last_contacted: date | None
    path: Path
    snoozed: bool


def compute_rows(
    *,
    today: date,
    include_below_threshold: bool,
    circle: str | None = None,
    include_snoozed: bool = False,
    limit: int | None = None,
    location: str | None = None,
    relationship_tag: str | None = None,
    interaction_preference: str | None = None,
) -> list[Row]:
    vault_root = vault.get_vault_root()
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError("limit must be a nonnegative integer")
    if circle is not None and circle not in person.CIRCLES:
        raise ValueError("unknown circle")
    report = validate.preflight(vault_root)
    if not report.ok:
        raise validate.ValidationError("preflight failed:\n  " + "\n  ".join(report.errors))
    cfg = config_mod.load(vault_root)
    rows: list[Row] = []
    above_threshold: list[Row] = []
    for p in people.matching_people(
        vault_root,
        circle=circle,
        location=location,
        relationship_tag=relationship_tag,
        interaction_preference=interaction_preference,
    ):
        if not p.periodic_contact_reminders and p.next_action_at is None:
            continue
        if p.next_action_at is not None:
            continue  # Manual actions appear in their own list, apart from cadence scoring.
        last = interactions.last_contacted(p)
        snoozed = bool(p.snooze_until and today < p.snooze_until)
        if snoozed and not include_snoozed:
            continue
        scored_person = replace(p, snooze_until=None) if include_snoozed else p
        s = score.score(scored_person, last=last, today=today, config=cfg)
        # No-cadence circles stay out of cadence scoring; manual actions and triage are separate.
        if cfg.circles[p.circle].cadence_days is None:
            continue
        days = (today - last).days if last else None
        do = score.days_overdue(scored_person, last=last, today=today, config=cfg)
        rows.append(
            Row(
                name=p.name,
                circle=p.circle,
                last_contacted=last,
                days=days,
                days_overdue=do,
                score=s,
                path=p.path.relative_to(vault_root),
                snoozed=snoozed,
                location=p.location,
                relationship_tags=p.relationship_tags,
                interaction_preferences=p.interaction_preferences,
            )
        )
        if score.in_queue(p, s, cfg):
            above_threshold.append(rows[-1])
    # Highest score first, including +inf at the very top.
    rows = sorted(
        rows if include_below_threshold else (above_threshold or rows),
        key=lambda r: (-r.score, r.last_contacted or date.min),
    )
    if not include_below_threshold and not above_threshold and limit is None:
        rows = rows[:10]
    if limit is not None:
        rows = rows[:limit]
    return rows


def _format_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return (
            "No eligible contacts match this queue (or --limit is 0). "
            "Check filters, snoozes, and reminder settings; "
            "use `fam list` to inspect people outside the queue."
        )
    header = (
        f"{'SCORE':>6}  {'CIRCLE':<8}  {'LAST_CONTACTED':<14}"
        f"  {'DAYS':>4}  {'DAYS_OVERDUE':>12}  PATH"
    )
    out = [header]
    for r in rows:
        score_str = "inf" if r["score"] == "inf" else f"{r['score']:6.2f}"
        last_str = r["last_contacted"] or "-"
        days = str(r["days"]) if r["days"] is not None else "-"
        do = str(r["days_overdue"]) if r["days_overdue"] is not None else "-"
        out.append(
            f"{score_str:>6}  {r['circle']:<8}  {last_str:<14}  {days:>4}  {do:>12}  {r['path']}"
        )
    return "\n".join(out)


def rows_as_dicts(rows: list[Row]) -> list[dict[str, Any]]:
    """Serialize queue rows for CLI and MCP, using valid JSON for infinite scores."""
    return [
        {
            "name": r.name,
            "circle": r.circle,
            "last_contacted": r.last_contacted.isoformat() if r.last_contacted else None,
            "days": r.days,
            "days_overdue": r.days_overdue,
            "score": ("inf" if r.score == float("inf") else r.score),
            "path": str(r.path),
            "snoozed": r.snoozed,
            "location": r.location,
            "relationship_tags": r.relationship_tags,
            "interaction_preferences": r.interaction_preferences,
        }
        for r in rows
    ]


def _one_shot_rows(
    *,
    today: date,
    circle: str | None,
    circles: tuple[str, ...],
    require_action: bool,
    include_snoozed: bool = False,
    limit: int | None = None,
    location: str | None = None,
    relationship_tag: str | None = None,
    interaction_preference: str | None = None,
) -> list[OneShotRow]:
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError("limit must be a nonnegative integer")
    if circle is not None and circle not in person.CIRCLES:
        raise ValueError("unknown circle")
    if circle is not None and circle not in circles:
        return []
    vault_root = vault.get_vault_root()
    rows = []
    for p in people.matching_people(
        vault_root,
        circle=circle if circle is not None else None,
        location=location,
        relationship_tag=relationship_tag,
        interaction_preference=interaction_preference,
    ):
        if p.circle not in circles or (require_action and p.next_action_at is None):
            continue
        snoozed = bool(p.snooze_until and today < p.snooze_until)
        if snoozed and not include_snoozed:
            continue
        rows.append(
            OneShotRow(
                name=p.name,
                circle=p.circle,
                next_action_at=p.next_action_at,
                last_contacted=interactions.last_contacted(p),
                path=p.path.relative_to(vault_root),
                snoozed=snoozed,
            )
        )
    rows.sort(
        key=lambda row: (
            row.next_action_at or date.max,
            row.name.casefold(),
            str(row.path),
        )
    )
    return rows[:10] if limit is None else rows[:limit]


def compute_triage_rows(
    *,
    today: date,
    circle: str | None = None,
    include_snoozed: bool = False,
    limit: int | None = None,
    location: str | None = None,
    relationship_tag: str | None = None,
    interaction_preference: str | None = None,
) -> list[OneShotRow]:
    """List people awaiting relationship classification, ordered by manual action date."""
    return _one_shot_rows(
        today=today,
        circle=circle,
        circles=("needs-triage",),
        require_action=False,
        include_snoozed=include_snoozed,
        limit=limit,
        location=location,
        relationship_tag=relationship_tag,
        interaction_preference=interaction_preference,
    )


def compute_action_rows(
    *,
    today: date,
    circle: str | None = None,
    include_snoozed: bool = False,
    limit: int | None = None,
    location: str | None = None,
    relationship_tag: str | None = None,
    interaction_preference: str | None = None,
) -> list[OneShotRow]:
    """List manual one-off actions, excluding triage people shown in their own list."""
    return _one_shot_rows(
        today=today,
        circle=circle,
        circles=tuple(circle for circle in person.CIRCLES if circle != "needs-triage"),
        require_action=True,
        include_snoozed=include_snoozed,
        limit=limit,
        location=location,
        relationship_tag=relationship_tag,
        interaction_preference=interaction_preference,
    )


def one_shot_rows_as_dicts(rows: list[OneShotRow]) -> list[dict[str, Any]]:
    return [
        {
            "name": row.name,
            "circle": row.circle,
            "next_action_at": row.next_action_at.isoformat() if row.next_action_at else None,
            "last_contacted": row.last_contacted.isoformat() if row.last_contacted else None,
            "path": str(row.path),
            "snoozed": row.snoozed,
        }
        for row in rows
    ]


def _format_one_shots(rows: list[dict[str, Any]], *, empty_message: str) -> str:
    if not rows:
        return empty_message
    return "\n".join(
        [
            "NEXT_ACTION_AT  NAME / PATH",
            *(
                f"{row['next_action_at'] or '-':<14}  "
                f"{row['name']} / {row['path']}"
                for row in rows
            ),
        ]
    )


def queues(
    *,
    today: date,
    include_below_threshold: bool = False,
    circle: str | None = None,
    include_snoozed: bool = False,
    limit: int | None = None,
    location: str | None = None,
    relationship_tag: str | None = None,
    interaction_preference: str | None = None,
) -> dict[str, Any]:
    """Combine independent contact and event queues for CLI and MCP."""
    contacts = compute_rows(
        today=today,
        include_below_threshold=include_below_threshold,
        circle=circle,
        include_snoozed=include_snoozed,
        limit=limit,
        location=location,
        relationship_tag=relationship_tag,
        interaction_preference=interaction_preference,
    )
    events = fam_events.upcoming(
        today=today,
        circle=circle,
        include_snoozed=include_snoozed,
        limit=limit,
        location=location,
        relationship_tag=relationship_tag,
        interaction_preference=interaction_preference,
    )
    triage = compute_triage_rows(
        today=today,
        circle=circle,
        include_snoozed=include_snoozed,
        limit=limit,
        location=location,
        relationship_tag=relationship_tag,
        interaction_preference=interaction_preference,
    )
    actions = compute_action_rows(
        today=today,
        circle=circle,
        include_snoozed=include_snoozed,
        limit=limit,
        location=location,
        relationship_tag=relationship_tag,
        interaction_preference=interaction_preference,
    )
    return {
        "contacts": rows_as_dicts(contacts),
        "actions": one_shot_rows_as_dicts(actions),
        "triage": one_shot_rows_as_dicts(triage),
        "events": events,
    }


def run(
    *,
    today: date,
    json_out: bool,
    include_below_threshold: bool = False,
    circle: str | None = None,
    include_snoozed: bool = False,
    limit: int | None = None,
    location: str | None = None,
    relationship_tag: str | None = None,
    interaction_preference: str | None = None,
) -> None:
    result = queues(
        today=today,
        include_below_threshold=include_below_threshold,
        circle=circle,
        include_snoozed=include_snoozed,
        limit=limit,
        location=location,
        relationship_tag=relationship_tag,
        interaction_preference=interaction_preference,
    )
    if json_out:
        print(_json.dumps(result, indent=2, allow_nan=False))
    else:
        print(_format_table(result["contacts"]))
        print(
            "\nOne-off actions\n"
            + _format_one_shots(result["actions"], empty_message="No one-off actions.")
        )
        print(
            "\nNeeds triage\n"
            + _format_one_shots(result["triage"], empty_message="No people need triage.")
        )
        print("\nImportant events\n" + fam_events.format_events(result["events"]))
