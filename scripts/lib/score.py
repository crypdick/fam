"""Score formula + queue filter. Pure functions; no I/O."""
from __future__ import annotations

import math
from datetime import date

from scripts.lib.config import Config
from scripts.lib.person import Person


def _cadence(person: Person, config: Config) -> int | None:
    if person.cadence_days_override is not None:
        return person.cadence_days_override
    return config.circles[person.circle].cadence_days


def score(person: Person, last: date | None, today: date, config: Config) -> float:
    circle_cfg = config.circles[person.circle]
    if circle_cfg.cadence_days is None:
        return float("-inf")
    if person.snooze_until and today < person.snooze_until:
        return float("-inf")
    cadence = _cadence(person, config) or 0
    if cadence <= 0:
        return float("-inf")
    if person.next_action_at is not None:
        anchor = person.next_action_at
    elif last is not None:
        anchor = last + _days(cadence)
    else:
        return float("inf")
    days = (today - anchor).days
    return days / cadence


def days_overdue(person: Person, last: date | None, today: date, config: Config) -> int | None:
    """Days past the anchor (negative when not yet due). None for passive/snoozed/never."""
    circle_cfg = config.circles[person.circle]
    if circle_cfg.cadence_days is None:
        return None
    if person.snooze_until and today < person.snooze_until:
        return None
    if person.next_action_at is not None:
        anchor = person.next_action_at
    elif last is not None:
        cadence = _cadence(person, config)
        if cadence is None or cadence <= 0:
            return None
        anchor = last + _days(cadence)
    else:
        return None
    return (today - anchor).days


def in_queue(person: Person, score: float, config: Config) -> bool:
    if score == float("-inf"):
        return False
    if math.isinf(score):
        return True
    threshold = config.circles[person.circle].alert_threshold
    if threshold is None:
        return False
    return score >= threshold


def _days(n: int):
    from datetime import timedelta
    return timedelta(days=n)
