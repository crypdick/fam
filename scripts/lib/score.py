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


def _active_cadence(person: Person, today: date, config: Config) -> int | None:
    if config.circles[person.circle].cadence_days is None:
        return None
    if person.snooze_until and today < person.snooze_until:
        return None
    cadence = _cadence(person, config)
    return cadence if cadence is not None and cadence > 0 else None


def _days_overdue(person: Person, last: date | None, today: date, cadence: int) -> int | None:
    if person.next_action_at is not None:
        return (today - person.next_action_at).days
    if last is not None:
        # Difference arithmetic works even when last + cadence exceeds date.max.
        return (today - last).days - cadence
    return None


def score(person: Person, last: date | None, today: date, config: Config) -> float:
    cadence = _active_cadence(person, today, config)
    if cadence is None:
        return float("-inf")
    days = _days_overdue(person, last, today, cadence)
    return float("inf") if days is None else days / cadence


def days_overdue(person: Person, last: date | None, today: date, config: Config) -> int | None:
    """Days past the anchor (negative when not yet due). None for inactive/snoozed/never."""
    cadence = _active_cadence(person, today, config)
    return None if cadence is None else _days_overdue(person, last, today, cadence)


def in_queue(person: Person, score: float, config: Config) -> bool:
    if score == float("-inf"):
        return False
    if math.isinf(score):
        return True
    threshold = config.circles[person.circle].alert_threshold
    if threshold is None:
        return False
    return score >= threshold
