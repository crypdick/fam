from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from scripts.cli import main
from scripts.fam_mcp import create_server
from scripts.lib import people, person


@pytest.fixture(autouse=True)
def selected_vault(vault_root: Path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault_root))


def save_events(events, name="Carol"):
    return people.update_person(f"People/@{name}.md", {"important_events": events})


def test_event_updates_roundtrip_preserve_notes_and_clear(vault_root: Path):
    path = vault_root / "People/@Alice.md"
    before = person.load(path)
    events = [{"name": "Birthday", "date": "05-20", "remind_days_before": 7}]
    assert save_events(events, "Alice")["important_events"] == events
    people.log_contact("People/@Alice.md", date(2026, 5, 15), "Coffee")
    loaded = person.load(path)
    assert loaded.extra == before.extra
    assert loaded.important_events == events
    assert "- 2026-04-22" in loaded.body
    people.update_person("People/@Alice.md", {}, ["important_events"])
    assert person.load(path).important_events == []


@pytest.mark.parametrize(
    "events",
    [
        None,
        {},
        ["Birthday"],
        [{"name": "Birthday"}],
        [{"name": "", "date": "05-20"}],
        [{"name": "Hi\nBye", "date": "05-20"}],
        [{"name": "Birthday", "date": "02-30"}],
        [{"name": "Birthday", "date": "2026-02-29"}],
        [{"name": "Birthday", "date": "20260520"}],
        [{"name": "Birthday", "date": "05-20", "remind_days_before": True}],
        [{"name": "Birthday", "date": "05-20", "remind_days_before": -1}],
        [{"name": "Birthday", "date": "05-20", "remind_days_befor": 2}],
    ],
)
def test_invalid_events_fail_without_writes(vault_root: Path, events):
    before = {p: p.read_bytes() for p in vault_root.rglob("*.md")}
    with pytest.raises((ValueError, person.PersonSchemaError)):
        save_events(events)
    assert {p: p.read_bytes() for p in vault_root.rglob("*.md")} == before


def test_cli_event_queue_and_today(vault_root: Path, capsys):
    events = [
        {"name": "Birthday", "date": "05-20", "remind_days_before": 7},
        {"name": "Interview", "date": "2026-05-15", "remind_days_before": 0},
    ]
    assert (
        main(["person", "update", "People/@Carol.md", "--important-events", json.dumps(events)])
        == 0
    )
    capsys.readouterr()
    before = {p: p.read_bytes() for p in vault_root.rglob("*.md")}
    assert main(["events", "--on-date", "2026-05-15", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert [(r["event"], r["date"], r["days_until"]) for r in rows] == [
        ("Interview", "2026-05-15", 0),
        ("Birthday", "2026-05-20", 5),
    ]
    assert rows[1]["reminder_at"] == "2026-05-13"
    assert main(["today", "--on-date", "2026-05-15", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["events"] == rows
    assert "Carol" not in [r["name"] for r in payload["contacts"]]
    assert main(["today", "--on-date", "2026-05-15"]) == 0
    assert "Birthday" in capsys.readouterr().out
    assert main(["events", "--on-date", "2026-05-12", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == []
    assert main(["events", "--on-date", "2026-05-12", "--days", "1", "--json"]) == 0
    assert [r["event"] for r in json.loads(capsys.readouterr().out)] == ["Birthday"]
    assert {p: p.read_bytes() for p in vault_root.rglob("*.md")} == before


@pytest.mark.parametrize(
    "today,expected",
    [
        ("2027-02-28", "2027-02-28"),
        ("2028-02-28", "2028-02-29"),
        ("2028-02-29", "2028-02-29"),
        ("2028-03-01", None),
    ],
)
def test_annual_leap_day(today, expected, capsys):
    save_events([{"name": "Birthday", "date": "02-29"}])
    assert main(["events", "--on-date", today, "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert [r["date"] for r in rows] == ([expected] if expected else [])


def test_year_boundary_one_off_expiry_and_snoozes(capsys):
    save_events(
        [
            {"name": "Anniversary", "date": "01-02"},
            {"name": "Past", "date": "2026-12-29"},
        ]
    )
    people.update_person(
        "People/@Carol.md", {"periodic_contact_reminders": False, "snooze_until": "2027-01-01"}
    )
    for options, expected in [([], []), (["--include-snoozed"], ["2027-01-02"])]:
        assert main(["events", "--on-date", "2026-12-30", "--json", *options]) == 0
        assert [r["date"] for r in json.loads(capsys.readouterr().out)] == expected
    assert main(["events", "--on-date", "2027-01-01", "--json"]) == 0
    assert [r["event"] for r in json.loads(capsys.readouterr().out)] == ["Anniversary"]


def test_event_validation_blocks_other_writes(vault_root: Path):
    path = vault_root / "People/@Carol.md"
    path.write_text("---\ncircle: passive\nimportant_events: nope\n---\n")
    before = (vault_root / "People/@Alice.md").read_bytes()
    assert main(["validate"]) == 1
    assert main(["person", "update", "People/@Alice.md", "--circle", "inner"]) == 1
    assert main(["events", "--json"]) == 1
    assert (vault_root / "People/@Alice.md").read_bytes() == before


def test_mcp_events_updates_today_and_clear():
    async def check():
        async with Client(create_server()) as client:
            await client.call_tool(
                "update_person",
                {
                    "path": "People/@Carol.md",
                    "important_events": [{"name": "Birthday", "date": "05-20"}],
                },
            )
            events = await client.call_tool("events", {"on_date": "2026-05-15"})
            assert events.data[0]["date"] == "2026-05-20"
            today = await client.call_tool("today", {"on_date": "2026-05-15"})
            assert today.data["events"] == events.data
            note = await client.call_tool("read_person", {"path": "People/@Carol.md"})
            assert note.data["important_events"][0]["name"] == "Birthday"
            with pytest.raises(ToolError):
                await client.call_tool(
                    "update_person",
                    {
                        "path": "People/@Carol.md",
                        "important_events": [{"name": "Birthday", "date": "02-30"}],
                    },
                )
            await client.call_tool(
                "update_person", {"path": "People/@Carol.md", "clear": ["important_events"]}
            )
            assert (await client.call_tool("events", {"on_date": "2026-05-15"})).data == []

    asyncio.run(check())


@pytest.mark.parametrize(
    "on_date,expected",
    [
        ("2026-05-13", ["2026-05-20"]),
        ("2026-05-20", ["2026-05-20"]),
        ("2026-05-21", []),
        ("2027-05-13", ["2027-05-20"]),
    ],
)
def test_reminder_window_boundaries_and_annual_rollover(on_date, expected, capsys):
    save_events([{"name": "Birthday", "date": "05-20"}])
    assert main(["events", "--on-date", on_date, "--json"]) == 0
    assert [r["date"] for r in json.loads(capsys.readouterr().out)] == expected


def test_today_event_filters_and_independent_limits(capsys):
    for name in ("Carol", "Alice"):
        save_events([{"name": "Birthday", "date": "05-20"}], name)
    people.update_person("People/@Carol.md", {"relationship_tags": ["friend"]})
    assert main(["today", "--on-date", "2026-05-15", "--tag", "FRIEND", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["contacts"] == []
    assert [r["name"] for r in payload["events"]] == ["Carol"]
    assert main(["today", "--on-date", "2026-05-15", "--limit", "1", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["contacts"]) == 1
    assert [r["name"] for r in payload["events"]] == ["Alice"]
    assert main(["events", "--on-date", "2026-05-15", "--limit", "0", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_unquoted_one_off_date_and_default_notice(vault_root: Path, capsys):
    path = vault_root / "People/@Carol.md"
    path.write_text(
        "---\ncircle: passive\nimportant_events:\n  - name: Interview\n    date: 2026-05-20\n---\n"
    )
    assert main(["events", "--on-date", "2026-05-15", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["reminder_at"] == "2026-05-13"
    people.update_person("People/@Carol.md", {"location": "Oakland"})
    assert person.load(path).important_events == [
        {"name": "Interview", "date": "2026-05-20", "remind_days_before": 7}
    ]


def test_large_preview_range_returns_error(capsys):
    assert main(["events", "--days", "999999999999"]) == 1
    assert "supported date range" in capsys.readouterr().err
