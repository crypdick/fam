from __future__ import annotations

import math
from datetime import date, timedelta
from pathlib import Path

import pytest

from scripts.lib import config, score
from scripts.lib.person import Person

TODAY = date(2026, 5, 1)


@pytest.fixture
def cfg() -> config.Config:
    return config.Config(
        circles={
            "passive": config.CircleConfig(cadence_days=None, alert_threshold=None),
            "inner": config.CircleConfig(cadence_days=7, alert_threshold=-0.2),
            "close": config.CircleConfig(cadence_days=30, alert_threshold=0.0),
            "orbit": config.CircleConfig(cadence_days=90, alert_threshold=0.2),
            "distant": config.CircleConfig(cadence_days=180, alert_threshold=0.5),
        },
        path=Path("/x/fam-circles.md"),
    )


def _person(circle: str = "close", **kw: object) -> Person:
    return Person(path=Path("/x/@x.md"), name="x", circle=circle, body="", **kw)  # type: ignore[arg-type]


def test_passive_returns_neg_inf(cfg: config.Config) -> None:
    p = _person(circle="passive")
    assert score.score(p, last=None, today=TODAY, config=cfg) == float("-inf")


def test_snoozed_returns_neg_inf(cfg: config.Config) -> None:
    p = _person(snooze_until=date(2030, 1, 1))
    assert score.score(p, last=date(2026, 4, 1), today=TODAY, config=cfg) == float("-inf")


def test_never_contacted_returns_pos_inf(cfg: config.Config) -> None:
    p = _person(circle="orbit")
    assert score.score(p, last=None, today=TODAY, config=cfg) == float("inf")


def test_due_today_is_zero(cfg: config.Config) -> None:
    p = _person(circle="close")
    last = TODAY - timedelta(days=30)
    assert math.isclose(score.score(p, last=last, today=TODAY, config=cfg), 0.0)


def test_one_cadence_overdue_is_one(cfg: config.Config) -> None:
    p = _person(circle="close")
    last = TODAY - timedelta(days=60)
    assert math.isclose(score.score(p, last=last, today=TODAY, config=cfg), 1.0)


def test_cadence_override_used(cfg: config.Config) -> None:
    p = _person(circle="close", cadence_days_override=10)
    last = TODAY - timedelta(days=20)
    assert math.isclose(score.score(p, last=last, today=TODAY, config=cfg), 1.0)


def test_next_action_at_overrides_anchor(cfg: config.Config) -> None:
    # next_action_at = today: 0 days overdue / 30 cadence = 0
    p = _person(circle="close", next_action_at=TODAY)
    assert math.isclose(score.score(p, last=date(2020, 1, 1), today=TODAY, config=cfg), 0.0)


def test_next_action_at_pulls_in_earlier(cfg: config.Config) -> None:
    p = _person(circle="distant", next_action_at=TODAY - timedelta(days=10))
    assert math.isclose(score.score(p, last=None, today=TODAY, config=cfg), 10 / 180)


def test_in_queue_filters_passive(cfg: config.Config) -> None:
    p = _person(circle="passive")
    assert not score.in_queue(p, score=float("-inf"), config=cfg)


def test_in_queue_respects_threshold(cfg: config.Config) -> None:
    p = _person(circle="orbit")
    assert not score.in_queue(p, score=0.1, config=cfg)
    assert score.in_queue(p, score=0.3, config=cfg)


def test_days_overdue_helper(cfg: config.Config) -> None:
    p = _person(circle="close")
    last = TODAY - timedelta(days=45)
    assert score.days_overdue(p, last=last, today=TODAY, config=cfg) == 15
