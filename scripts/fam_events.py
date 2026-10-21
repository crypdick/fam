"""Important-event reminders, independent of contact cadence."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any

from scripts.lib import people, validate, vault


def upcoming(
    *,
    today: date,
    days: int = 0,
    include_snoozed: bool = False,
    limit: int | None = None,
    circle: str | None = None,
    location: str | None = None,
    relationship_tag: str | None = None,
    interaction_preference: str | None = None,
) -> list[dict[str, Any]]:
    """Return next occurrences whose reminder window starts by today + days."""
    if type(days) is not int or days < 0:
        raise ValueError("days must be a nonnegative integer")
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError("limit must be a nonnegative integer")
    if days > (date.max - today).days:
        raise ValueError("days exceeds the supported date range")
    horizon = today + timedelta(days=days)
    root = vault.get_vault_root()
    report = validate.preflight(root)
    if not report.ok:
        raise validate.ValidationError("preflight failed:\n  " + "\n  ".join(report.errors))
    rows = []
    for p in people.matching_people(
        root,
        circle=circle,
        location=location,
        relationship_tag=relationship_tag,
        interaction_preference=interaction_preference,
    ):
        snoozed = bool(p.snooze_until and today < p.snooze_until)
        if snoozed and not include_snoozed:
            continue
        for event in p.important_events:
            value = event["date"]
            if len(value) == 5:
                month, day = map(int, value.split("-"))
                year = today.year
                occurrence = date(year, month, min(day, calendar.monthrange(year, month)[1]))
                if occurrence < today:
                    if year == date.max.year:
                        continue
                    year += 1
                    occurrence = date(year, month, min(day, calendar.monthrange(year, month)[1]))
            else:
                occurrence = date.fromisoformat(value)
            reminder_at = date.fromordinal(
                max(1, occurrence.toordinal() - event["remind_days_before"])
            )
            if occurrence < today or reminder_at > horizon:
                continue
            rows.append(
                {
                    "name": p.name,
                    "circle": p.circle,
                    "path": str(p.path.relative_to(root)),
                    "event": event["name"],
                    "date": occurrence.isoformat(),
                    "reminder_at": reminder_at.isoformat(),
                    "days_until": (occurrence - today).days,
                    "snoozed": snoozed,
                }
            )
    rows.sort(key=lambda row: (row["date"], row["name"].casefold(), row["path"], row["event"]))
    return rows if limit is None else rows[:limit]


def format_events(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No important event reminders match this queue."
    return "\n".join(
        [
            "DATE        DAYS  NAME / EVENT / PATH",
            *(
                f"{r['date']}  {r['days_until']:>4}  {r['name']} / {r['event']} / {r['path']}"
                for r in rows
            ),
        ]
    )
