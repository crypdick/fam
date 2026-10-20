from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from scripts.lib import interactions, person


@pytest.fixture(autouse=True)
def selected_vault(vault_root: Path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault_root))


def run(*args: str) -> int:
    from scripts.cli import main

    return main(list(args))


def test_list_show_and_queue(vault_root: Path, capsys):
    assert run("person", "list", "--circle", "passive") == 0
    assert json.loads(capsys.readouterr().out) == [
        {"name": "Carol", "circle": "passive", "last_contacted": None, "path": "People/@Carol.md"}
    ]
    assert run("person", "show", "People/@Alice.md") == 0
    assert (
        json.loads(capsys.readouterr().out)["content"]
        == (vault_root / "People/@Alice.md").read_text()
    )
    before = {p: p.read_bytes() for p in vault_root.rglob("*.md")}
    assert run("today", "--on-date", "2026-05-15", "--limit", "1", "--json") == 0
    assert json.loads(capsys.readouterr().out)[0]["name"] == "Dan"
    assert {p: p.read_bytes() for p in vault_root.rglob("*.md")} == before


def test_log_contact_preserves_context_and_requires_explicit_action_completion(vault_root: Path):
    path = vault_root / "People/@Alice.md"
    path.write_text(
        path.read_text().replace(
            "circle: close", "circle: close\nprofession: dev\nnext_action_at: 2026-05-01"
        )
        + "\nKeep this context.\n"
    )
    assert (
        run(
            "person",
            "log-contact",
            "People/@Alice.md",
            "--date",
            "2026-05-15",
            "--description",
            "Lunch",
        )
        == 0
    )
    loaded = person.load(path)
    assert loaded.next_action_at == date(2026, 5, 1)
    assert loaded.extra["profession"] == "dev"
    assert "Keep this context." in loaded.body
    assert interactions.last_contacted(loaded) == date(2026, 5, 15)
    assert "- 2026-05-15 — Lunch" in loaded.body.split("## Other references")[0]
    assert (
        run(
            "person",
            "log-contact",
            "People/@Alice.md",
            "--date",
            "2026-05-15",
            "--description",
            "Lunch",
            "--complete-action",
        )
        == 0
    )
    loaded = person.load(path)
    assert loaded.next_action_at is None
    assert loaded.body.count("- 2026-05-15 — Lunch") == 1
    assert "last_contacted:" not in path.read_text()


@pytest.mark.parametrize("body", ["# Context\nKeep me.", "```md\n## Logged contacts\n```\n"])
def test_logging_creates_missing_section(vault_root: Path, body):
    path = vault_root / "People/@Carol.md"
    path.write_text("---\ncircle: passive\n---\n\n" + body)
    assert (
        run(
            "person",
            "log-contact",
            "People/@Carol.md",
            "--date",
            "2026-05-15",
            "--description",
            "Coffee",
        )
        == 0
    )
    assert interactions.last_contacted(person.load(path)) == date(2026, 5, 15)
    assert body in person.load(path).body


@pytest.mark.parametrize("body", ["## Logged contacts\n\n## Logged contacts\n", "```md\nexample"])
def test_logging_rejects_ambiguous_or_unclosed_sections(vault_root: Path, body):
    path = vault_root / "People/@Carol.md"
    path.write_text("---\ncircle: passive\n---\n\n" + body)
    before = path.read_bytes()
    assert (
        run(
            "person",
            "log-contact",
            "People/@Carol.md",
            "--date",
            "2026-05-15",
            "--description",
            "Coffee",
        )
        == 1
    )
    assert path.read_bytes() == before


def test_update_fields_and_explicit_removal(vault_root: Path):
    path = vault_root / "People/@Alice.md"
    path.write_text(path.read_text().replace("circle: close", "circle: close\nprofession: dev"))
    body = person.load(path).body
    assert (
        run(
            "person",
            "update",
            "People/@Alice.md",
            "--circle",
            "inner",
            "--cadence-days-override",
            "14",
            "--snooze-until",
            "2026-06-01",
            "--next-action-at",
            "2026-06-02",
            "--no-periodic-contact-reminders",
            "--contact-channels-ordered-preference",
            "signal",
            "email",
        )
        == 0
    )
    loaded = person.load(path)
    assert (loaded.circle, loaded.cadence_days_override) == ("inner", 14)
    assert loaded.snooze_until == date(2026, 6, 1)
    assert loaded.next_action_at == date(2026, 6, 2)
    assert loaded.periodic_contact_reminders is False
    assert loaded.contact_channels_ordered_preference == ["signal", "email"]
    assert loaded.extra == {"profession": "dev"}
    assert loaded.body == body
    assert run("person", "update", "People/@Alice.md", "--circle", "orbit") == 0
    assert person.load(path).cadence_days_override == 14
    assert (
        run(
            "person",
            "update",
            "People/@Alice.md",
            "--clear",
            "cadence_days_override",
            "--clear",
            "snooze_until",
            "--clear",
            "next_action_at",
            "--clear",
            "periodic_contact_reminders",
            "--clear",
            "contact_channels_ordered_preference",
        )
        == 0
    )
    loaded = person.load(path)
    assert loaded.cadence_days_override is None
    assert loaded.snooze_until is None
    assert loaded.next_action_at is None
    assert loaded.periodic_contact_reminders is True
    assert loaded.contact_channels_ordered_preference == []


def test_missing_circle_requires_explicit_targeted_repair(vault_root: Path, capsys):
    path = vault_root / "People/@Carol.md"
    path.write_text("---\nprofession: dev\n---\n\n## Logged contacts\n")
    before = path.read_bytes()
    assert run("today", "--json") == 1
    assert "missing required field `circle`" in capsys.readouterr().err
    assert path.read_bytes() == before
    assert run("person", "update", "People/@Carol.md", "--circle", "reference") == 0
    assert person.load(path).circle == "reference"
    assert person.load(path).extra == {"profession": "dev"}
    assert run("validate") == 0


def test_mutations_stop_on_other_invalid_notes(vault_root: Path):
    (vault_root / "People/@Invalid.md").write_text("---\ncircle: nonsense\n---\n")
    path = vault_root / "People/@Alice.md"
    before = path.read_bytes()
    assert run("person", "update", "People/@Alice.md", "--circle", "inner") == 1
    assert (
        run(
            "person",
            "log-contact",
            "People/@Alice.md",
            "--date",
            "2026-05-15",
            "--description",
            "Coffee",
        )
        == 1
    )
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "args",
    [
        ("person", "update", "People/@Alice.md", "--cadence-days-override", "0"),
        ("person", "update", "People/@Alice.md", "--snooze-until", "20260515"),
        ("person", "update", "People/@Alice.md", "--clear", "circle"),
        (
            "person",
            "log-contact",
            "People/@Alice.md",
            "--date",
            "2026-02-30",
            "--description",
            "Coffee",
        ),
        ("person", "log-contact", "People/@Alice.md", "--description", "Coffee"),
        ("today", "--limit", "-1"),
        ("today", "--circle", "unknown"),
        ("tend",),
    ],
)
def test_invalid_cli_arguments_do_not_write(vault_root: Path, args):
    before = {p: p.read_bytes() for p in vault_root.rglob("*.md")}
    with pytest.raises(SystemExit) as error:
        run(*args)
    assert error.value.code == 2
    assert {p: p.read_bytes() for p in vault_root.rglob("*.md")} == before


@pytest.mark.parametrize(
    "path", ["../@Escape.md", "/etc/passwd", "fam-circles.md", ".trash/@Alice.md"]
)
def test_person_writes_reject_non_person_paths(vault_root: Path, path):
    before = {p: p.read_bytes() for p in vault_root.rglob("*.md")}
    assert run("person", "update", path, "--circle", "inner") == 1
    assert {p: p.read_bytes() for p in vault_root.rglob("*.md")} == before


@pytest.mark.parametrize(
    "options",
    [[], ["--circle", "inner", "--clear", "snooze_until", "--snooze-until", "2026-06-01"]],
)
def test_update_requires_unambiguous_changes(vault_root: Path, options):
    path = vault_root / "People/@Alice.md"
    before = path.read_bytes()
    assert run("person", "update", "People/@Alice.md", *options) == 1
    assert path.read_bytes() == before


def test_ensure_and_explicit_scan_preview(vault_root: Path, capsys):
    (vault_root / "Notes/new.md").write_text("[[@New Person]] and [[@Other Person]]")
    before = {p: p.read_bytes() for p in vault_root.rglob("*.md")}
    assert run("person", "ensure", "New Person", "--dry-run") == 0
    assert json.loads(capsys.readouterr().out)["planned"] == ["@New Person"]
    assert run("tend", "--scan", "--dry-run") == 0
    assert json.loads(capsys.readouterr().out)["planned"] == ["@New Person", "@Other Person"]
    assert {p: p.read_bytes() for p in vault_root.rglob("*.md")} == before


def test_circle_repair_does_not_ignore_other_missing_circles(vault_root: Path):
    for name in ("Carol", "Dan"):
        (vault_root / f"People/@{name}.md").write_text("---\nprofession: dev\n---\n")
    before = {p: p.read_bytes() for p in vault_root.rglob("*.md")}
    assert run("person", "update", "People/@Carol.md", "--circle", "reference") == 1
    assert {p: p.read_bytes() for p in vault_root.rglob("*.md")} == before


def test_unconfigured_circle_is_rejected_before_writing(vault_root: Path):
    config = vault_root / "fam-circles.md"
    config.write_text(
        "\n".join(line for line in config.read_text().splitlines() if "distant:" not in line)
    )
    path = vault_root / "People/@Alice.md"
    before = path.read_bytes()
    assert run("person", "update", "People/@Alice.md", "--circle", "distant") == 1
    assert path.read_bytes() == before


def test_person_writes_reject_symlink_escape(vault_root: Path, tmp_path: Path):
    outside = tmp_path / "@Outside.md"
    outside.write_text("---\ncircle: close\n---\n\nPrivate context.")
    (vault_root / "People/@Outside.md").symlink_to(outside)
    before = outside.read_bytes()
    assert run("person", "update", "People/@Outside.md", "--circle", "inner") == 1
    assert (
        run(
            "person",
            "log-contact",
            "People/@Outside.md",
            "--date",
            "2026-05-15",
            "--description",
            "Coffee",
        )
        == 1
    )
    assert outside.read_bytes() == before


def test_contact_date_is_derived_from_latest_not_append_order(vault_root: Path):
    assert (
        run(
            "person",
            "log-contact",
            "People/@Alice.md",
            "--date",
            "2026-04-10",
            "--description",
            "Earlier call",
        )
        == 0
    )
    loaded = person.load(vault_root / "People/@Alice.md")
    assert interactions.last_contacted(loaded) == date(2026, 4, 22)
    assert "- 2026-04-10 — Earlier call" in loaded.body


def test_failed_circle_repair_reports_proposed_value_without_writing(vault_root: Path, capsys):
    config = vault_root / "fam-circles.md"
    config.write_text(
        "\n".join(line for line in config.read_text().splitlines() if "distant:" not in line)
    )
    path = vault_root / "People/@Carol.md"
    path.write_text("---\nprofession: dev\n---\n")
    before = path.read_bytes()
    assert run("person", "update", "People/@Carol.md", "--circle", "distant") == 1
    assert "circle 'distant' is not configured" in capsys.readouterr().err
    assert path.read_bytes() == before
