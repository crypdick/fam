from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path

import pytest
from fastmcp import Client

from scripts.cli import main
from scripts.fam_mcp import create_server
from scripts.lib import person


@pytest.fixture
def metadata_vault(vault_root: Path, monkeypatch) -> Path:
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault_root))
    for name in ("Alice", "Bob", "Carol", "Eve"):
        path = vault_root / f"People/@{name}.md"
        text = path.read_text()
        text = text.replace(
            "---\n",
            "---\nlocation: Straße, San Francisco\n"
            "relationship_tags: [Friend]\n"
            "interaction_preferences: [In_Person, text]\n",
            1,
        )
        if name == "Bob":
            text = text.replace("circle: inner", "circle: inner\nperiodic_contact_reminders: false")
        path.write_text(text)
    return vault_root


@pytest.mark.parametrize(
    "arguments,expected",
    [
        (["--location", "francisco"], ["Alice"]),
        (["--location", "STRASSE"], ["Alice"]),
        (["--location", "Oakland"], []),
        (["--tag", "friend"], ["Alice"]),
        (["--tag", "fri"], []),
        (["--tag", "family"], []),
        (["--interaction", "in_person"], ["Alice"]),
        (["--interaction", "in"], []),
        (["--interaction", "call"], []),
        (
            ["--location", "san francisco", "--tag", "FRIEND", "--interaction", "IN_PERSON"],
            ["Alice"],
        ),
        (["--location", "san francisco", "--tag", "family", "--interaction", "IN_PERSON"], []),
        (["--tag", "friend", "--include-snoozed"], ["Eve", "Alice"]),
    ],
)
def test_cli_metadata_filters_keep_queue_exclusions(metadata_vault, capsys, arguments, expected):
    before = {p: p.read_bytes() for p in metadata_vault.rglob("*.md")}
    assert main(["today", "--on-date", "2026-05-15", "--all", "--json", *arguments]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert [row["name"] for row in rows] == expected
    assert {p: p.read_bytes() for p in metadata_vault.rglob("*.md")} == before
    for row in rows:
        assert row["location"] == "Straße, San Francisco"
        assert row["relationship_tags"] == ["Friend"]
        assert row["interaction_preferences"] == ["In_Person", "text"]


def test_metadata_filters_allow_fallback_within_eligible_matches(metadata_vault, capsys):
    assert main(["today", "--on-date", "2026-05-15", "--json", "--tag", "friend"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert [row["name"] for row in rows] == ["Alice"]
    assert rows[0]["score"] < 0


@pytest.mark.parametrize(
    "arguments,expected",
    [
        (["--location", "STRASSE"], ["Alice", "Bob", "Carol", "Eve"]),
        (["--tag", "FRIEND", "--limit", "2"], ["Alice", "Bob"]),
        (["--tag", "fri"], []),
        (["--interaction", "IN_PERSON", "--circle", "passive"], ["Carol"]),
        (["--location", "francisco", "--tag", "family"], []),
        (["--interaction", "call"], []),
    ],
)
def test_full_list_metadata_filters(metadata_vault, capsys, arguments, expected):
    assert main(["list", "--json", *arguments]) == 0
    assert [row["name"] for row in json.loads(capsys.readouterr().out)] == expected


@pytest.mark.parametrize(
    "field,value",
    [
        ("location", "[San Francisco]"),
        ("relationship_tags", "friend"),
        ("relationship_tags", "[1]"),
        ("interaction_preferences", "in_person"),
        ("interaction_preferences", "false"),
        ("contact_channels_ordered_preference", "null"),
    ],
)
def test_person_rejects_invalid_metadata_without_loosening_channels(vault_root, field, value):
    path = vault_root / "People/@Carol.md"
    path.write_text(f"---\ncircle: passive\n{field}: {value}\n---\n")
    with pytest.raises(person.PersonSchemaError, match=field):
        person.load(path)


def test_cli_metadata_updates_clear_and_contact_preservation(vault_root, monkeypatch, capsys):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault_root))
    path = vault_root / "People/@Alice.md"
    path.write_text(path.read_text().replace("circle: close", "circle: close\nprofession: dev"))
    assert (
        main(
            [
                "person",
                "update",
                "People/@Alice.md",
                "--location",
                "San Francisco",
                "--relationship-tags",
                "friend",
                "family",
                "--interaction-preferences",
                "in_person",
                "text",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["location"] == "San Francisco"
    assert result["relationship_tags"] == ["friend", "family"]
    assert result["interaction_preferences"] == ["in_person", "text"]
    assert (
        main(
            [
                "person",
                "log-contact",
                "People/@Alice.md",
                "--date",
                "2026-05-15",
                "--description",
                "Coffee",
            ]
        )
        == 0
    )
    loaded = person.load(path)
    assert loaded.location == "San Francisco"
    assert loaded.relationship_tags == ["friend", "family"]
    assert loaded.interaction_preferences == ["in_person", "text"]
    assert loaded.extra == {"profession": "dev"}
    assert (
        main(
            [
                "person",
                "update",
                "People/@Alice.md",
                "--clear",
                "location",
                "--clear",
                "relationship_tags",
                "--clear",
                "interaction_preferences",
            ]
        )
        == 0
    )
    loaded = person.load(path)
    assert loaded.location is None
    assert loaded.relationship_tags == []
    assert loaded.interaction_preferences == []
    assert loaded.extra == {"profession": "dev"}


def test_mcp_metadata_filter_update_read_and_clear(metadata_vault):
    async def check():
        async with Client(create_server()) as client:
            queue = await client.call_tool(
                "today",
                {
                    "on_date": "2026-05-15",
                    "include_below_threshold": True,
                    "location": "san francisco",
                    "relationship_tag": "friend",
                    "interaction_preference": "in_person",
                },
            )
            assert [row["name"] for row in queue.data] == ["Alice"]
            assert queue.data[0]["location"] == "Straße, San Francisco"
            result = await client.call_tool(
                "update_person",
                {
                    "path": "People/@Alice.md",
                    "location": "Oakland",
                    "relationship_tags": ["friend", "climbing"],
                    "interaction_preferences": ["call"],
                },
            )
            assert result.data["location"] == "Oakland"
            read = await client.call_tool("read_person", {"path": "People/@Alice.md"})
            assert read.data["relationship_tags"] == ["friend", "climbing"]
            assert read.data["interaction_preferences"] == ["call"]
            people = await client.call_tool("list_people", {"circle": "close"})
            assert (
                next(row for row in people.data if row["name"] == "Alice")["location"] == "Oakland"
            )
            filtered = await client.call_tool(
                "list_people", {"relationship_tag": "FRIEND", "location": "strasse", "limit": 2}
            )
            assert [row["name"] for row in filtered.data] == ["Bob", "Carol"]
            ranked = await client.call_tool(
                "list_people",
                {"sort_by": "score", "on_date": "2026-05-15", "relationship_tag": "friend"},
            )
            assert [row["name"] for row in ranked.data] == ["Bob", "Alice", "Carol", "Eve"]
            assert ranked.data[0]["score"] == pytest.approx(13 / 7)
            await client.call_tool(
                "update_person",
                {
                    "path": "People/@Alice.md",
                    "clear": ["location", "relationship_tags", "interaction_preferences"],
                },
            )

    asyncio.run(check())
    loaded = person.load(metadata_vault / "People/@Alice.md")
    assert loaded.location is None
    assert loaded.relationship_tags == []
    assert loaded.interaction_preferences == []
    assert loaded.next_action_at is None
    assert loaded.contact_channels_ordered_preference == ["imessage", "email"]
    assert date(2026, 4, 22).isoformat() in loaded.body
