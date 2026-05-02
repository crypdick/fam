from __future__ import annotations

from datetime import date
from pathlib import Path

from scripts.lib import interactions, person


def test_parse_alice_returns_two_dates(vault_root: Path) -> None:
    p = person.load(vault_root / "People" / "@Alice.md")
    bullets = interactions.parse_logged_contacts(p.body)
    dates = [b.date for b in bullets]
    assert dates == [date(2026, 4, 22), date(2026, 4, 1)]


def test_last_contacted_picks_max(vault_root: Path) -> None:
    p = person.load(vault_root / "People" / "@Alice.md")
    assert interactions.last_contacted(p) == date(2026, 4, 22)


def test_last_contacted_none_when_no_section() -> None:
    p = person.Person(
        path=Path("/x/@X.md"),
        name="X",
        circle="close",
        body="# title\n\nno section\n",
    )
    assert interactions.last_contacted(p) is None


def test_last_contacted_none_when_section_empty(vault_root: Path) -> None:
    p = person.load(vault_root / "People" / "@Carol.md")
    assert interactions.last_contacted(p) is None


def test_malformed_bullet_skipped() -> None:
    body = (
        "## Logged contacts\n"
        "- 2026-04-01 — valid\n"
        "- not a date — bogus\n"
        "- 2026-not-a-date — bogus\n"
        "- 2026-05-01 — valid\n"
    )
    bullets = interactions.parse_logged_contacts(body)
    dates = [b.date for b in bullets]
    assert dates == [date(2026, 4, 1), date(2026, 5, 1)]


def test_extra_whitespace_tolerated() -> None:
    body = "## Logged contacts\n-   2026-04-01   —    text\n"
    bullets = interactions.parse_logged_contacts(body)
    assert bullets[0].date == date(2026, 4, 1)
    assert bullets[0].text == "text"


def test_em_or_en_dash_either_accepted() -> None:
    body = "## Logged contacts\n- 2026-04-01 - text\n- 2026-04-02 — text\n- 2026-04-03 – text\n"
    bullets = interactions.parse_logged_contacts(body)
    assert [b.date for b in bullets] == [date(2026, 4, 1), date(2026, 4, 2), date(2026, 4, 3)]
