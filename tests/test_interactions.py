from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

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


def test_headings_and_contacts_in_fenced_examples_are_ignored():
    body = (
        "```md\n## Logged contacts\n- 2030-01-01 — example\n```\n"
        "## Logged contacts\n- 2026-05-01 — real contact\n"
        "~~~md\n- 2030-02-01 — another example\n~~~\n"
        "# Another topic\n- 2030-03-01 — outside contact history\n"
    )
    assert interactions.parse_logged_contacts(body) == [
        interactions.LoggedContact(date=date(2026, 5, 1), text="real contact")
    ]
    assert interactions.logged_contact_errors(body) == []


def test_duplicate_sections_rejected_by_reads_validation_and_append():
    body = (
        "## Logged contacts\n- 2020-01-01 — older\n"
        "## Other references\ncontext\n"
        "## Logged contacts\n- 2026-11-01 — newer\n"
    )
    assert interactions.logged_contact_errors(body) == [
        "multiple Logged contacts sections; resolve before logging"
    ]
    with pytest.raises(ValueError, match="multiple Logged contacts"):
        interactions.parse_logged_contacts(body)
    with pytest.raises(ValueError, match="multiple Logged contacts"):
        interactions.append_contact(body, date(2026, 11, 2), "Coffee")


@pytest.mark.parametrize(
    "bullet",
    ["-\tbad", "* 2026-05-01 — unsupported marker", "+ bad", "- 2026-05-01 —", "-"],
)
def test_malformed_bullet_grammar_shared_with_append(bullet):
    body = "## Logged contacts\n" + bullet + "\n"
    assert interactions.parse_logged_contacts(body) == []
    assert interactions.logged_contact_errors(body) == [
        f"malformed logged contact at body line 2: {bullet}"
    ]
    with pytest.raises(ValueError, match="malformed logged contact"):
        interactions.append_contact(body, date(2026, 11, 2), "Coffee")


def test_tab_separator_and_subheading_preserve_contact_section():
    body = (
        "## Logged contacts\n### In person\n-\t2026-05-01 — Coffee\n"
        "## Other references\n- not a contact\n"
    )
    result = interactions.append_contact(body, date(2026, 11, 2), "Lunch")
    assert interactions.parse_logged_contacts(result) == [
        interactions.LoggedContact(date(2026, 5, 1), "Coffee"),
        interactions.LoggedContact(date(2026, 11, 2), "Lunch"),
    ]
    assert interactions.logged_contact_errors(result) == []
    assert result.endswith("## Other references\n- not a contact")


@pytest.mark.parametrize("description", ["", "  ", "Coffee\nLunch", "Coffee\x00"])
def test_append_rejects_invalid_description(description):
    with pytest.raises(ValueError, match="description must be a nonempty single line"):
        interactions.append_contact("", date(2026, 11, 2), description)
