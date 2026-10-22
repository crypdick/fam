from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest


@patch("scripts.lib.vault.get_vault_root")
def test_today_default_includes_overdue(mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    from scripts import fam_today

    rows = fam_today.compute_rows(today=date(2026, 5, 15), include_below_threshold=False)
    names = {r.name for r in rows}
    assert "Bob" in names  # inner cadence 7, last 2026-04-25 → overdue
    assert "Carol" not in names  # passive
    assert "Dan" in names  # never contacted → +inf


@patch("scripts.lib.vault.get_vault_root")
def test_today_excludes_snoozed(mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    from scripts import fam_today

    rows = fam_today.compute_rows(today=date(2026, 5, 15), include_below_threshold=False)
    assert all(r.name != "Eve" for r in rows)


@patch("scripts.lib.vault.get_vault_root")
def test_today_all_includes_below_threshold(mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    from scripts import fam_today

    today = date(2026, 4, 25)
    rows = fam_today.compute_rows(today=today, include_below_threshold=True)
    names = {r.name for r in rows}
    # Alice was contacted 2026-04-22 and is in `close` (cadence 30) — far below threshold.
    # With --all she shows up.
    assert "Alice" in names


@patch("scripts.lib.vault.get_vault_root")
def test_today_circle_filter(mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    from scripts import fam_today

    rows = fam_today.compute_rows(
        today=date(2026, 5, 15), include_below_threshold=True, circle="orbit"
    )
    assert {r.name for r in rows} == {"Dan"}


@patch("scripts.lib.vault.get_vault_root")
def test_today_json_output_has_required_keys(mock_root, vault_root: Path, capsys) -> None:
    mock_root.return_value = vault_root
    from scripts import fam_today

    fam_today.run(today=date(2026, 5, 15), json_out=True)
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload  # non-empty
    assert payload["events"] == []
    assert payload["actions"] == []
    assert payload["triage"] == []
    row = payload["contacts"][0]
    assert {
        "name",
        "circle",
        "last_contacted",
        "days",
        "days_overdue",
        "score",
        "path",
    } <= row.keys()


@patch("scripts.lib.vault.get_vault_root")
def test_today_table_includes_days_overdue_column(mock_root, vault_root: Path, capsys) -> None:
    mock_root.return_value = vault_root
    from scripts import fam_today

    fam_today.run(today=date(2026, 5, 15), json_out=False)
    captured = capsys.readouterr()
    assert "DAYS_OVERDUE" in captured.out


@patch("scripts.lib.vault.get_vault_root")
def test_today_surfaces_triage_people_separately(mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    (vault_root / "People" / "@Needs Action.md").write_text(
        "---\ncircle: needs-triage\nnext_action_at: 2026-05-14\n---\n"
        "\n## Logged contacts\n- 2026-05-01 — message\n"
    )
    (vault_root / "People" / "@Needs Review.md").write_text(
        "---\ncircle: needs-triage\n---\n\n## Logged contacts\n"
    )
    from scripts import fam_today

    result = fam_today.queues(today=date(2026, 5, 15))

    assert [row["name"] for row in result["triage"]] == ["Needs Action", "Needs Review"]
    assert result["triage"][0]["next_action_at"] == "2026-05-14"
    assert result["triage"][0]["path"] == "People/@Needs Action.md"
    assert all(row["circle"] == "needs-triage" for row in result["triage"])
    assert all(row["name"] != "Needs Action" for row in result["contacts"])


@patch("scripts.lib.vault.get_vault_root")
def test_today_triage_respects_circle_filter_limit_and_snooze(mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    (vault_root / "People" / "@Needs Action.md").write_text(
        "---\ncircle: needs-triage\nnext_action_at: 2026-05-14\n---\n"
        "\n## Logged contacts\n"
    )
    (vault_root / "People" / "@Snoozed.md").write_text(
        "---\ncircle: needs-triage\nsnooze_until: 2026-06-01\n---\n"
        "\n## Logged contacts\n"
    )
    from scripts import fam_today

    result = fam_today.queues(today=date(2026, 5, 15), circle="needs-triage", limit=1)
    assert [row["name"] for row in result["triage"]] == ["Needs Action"]
    assert fam_today.queues(today=date(2026, 5, 15), circle="passive")["triage"] == []


@patch("scripts.lib.vault.get_vault_root")
def test_today_surfaces_manual_actions_separately(mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    (vault_root / "People" / "@Passive Action.md").write_text(
        "---\ncircle: passive\nnext_action_at: 2026-05-14\n---\n"
        "\n## Logged contacts\n"
    )
    (vault_root / "People" / "@Reference Action.md").write_text(
        "---\ncircle: reference\nnext_action_at: 2026-05-16\n---\n"
        "\n## Logged contacts\n"
    )
    (vault_root / "People" / "@Active Action.md").write_text(
        "---\ncircle: close\nnext_action_at: 2026-05-15\n---\n"
        "\n## Logged contacts\n"
    )
    from scripts import fam_today

    result = fam_today.queues(today=date(2026, 5, 15))

    assert [row["name"] for row in result["actions"]] == [
        "Passive Action",
        "Active Action",
        "Reference Action",
    ]
    assert result["actions"][0]["next_action_at"] == "2026-05-14"
    assert result["actions"][2]["circle"] == "reference"
    assert all(row["name"] != "Active Action" for row in result["contacts"])
    filtered = fam_today.queues(today=date(2026, 5, 15), circle="passive")
    assert [row["name"] for row in filtered["actions"]] == ["Passive Action"]


@patch("scripts.lib.vault.get_vault_root")
def test_today_excludes_periodic_muted(mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    (vault_root / "People" / "@Greta.md").write_text(
        "---\ncircle: inner\nperiodic_contact_reminders: false\n---\n\n## Logged contacts\n"
    )
    from scripts import fam_today

    rows = fam_today.compute_rows(today=date(2026, 5, 15), include_below_threshold=False)
    assert all(r.name != "Greta" for r in rows)


@patch("scripts.lib.vault.get_vault_root")
def test_today_all_still_excludes_periodic_muted(mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    (vault_root / "People" / "@Greta.md").write_text(
        "---\ncircle: inner\nperiodic_contact_reminders: false\n---\n\n## Logged contacts\n"
    )
    from scripts import fam_today

    rows = fam_today.compute_rows(today=date(2026, 5, 15), include_below_threshold=True)
    assert all(r.name != "Greta" for r in rows)


@patch("scripts.lib.vault.get_vault_root")
def test_today_includes_periodic_muted_with_next_action_at(mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    (vault_root / "People" / "@Greta.md").write_text(
        "---\ncircle: inner\nperiodic_contact_reminders: false\n"
        "next_action_at: 2026-05-15\n---\n\n## Logged contacts\n"
    )
    from scripts import fam_today

    result = fam_today.queues(today=date(2026, 5, 15))
    assert any(row["name"] == "Greta" for row in result["actions"])
    assert all(row["name"] != "Greta" for row in result["contacts"])


@patch("scripts.lib.vault.get_vault_root")
def test_today_rejects_missing_circle_without_writing(mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    missing_circle = vault_root / "People" / "@Greta.md"
    missing_circle.write_text("---\nprofession: dev\n---\n\n## Logged contacts\n")

    from scripts import fam_today
    from scripts.lib import validate

    before = missing_circle.read_bytes()
    with pytest.raises(validate.ValidationError, match="missing required field `circle`"):
        fam_today.compute_rows(today=date(2026, 5, 15), include_below_threshold=True)
    assert missing_circle.read_bytes() == before


@patch("scripts.lib.vault.get_vault_root")
def test_today_include_snoozed_keeps_real_scores_and_valid_json(mock_root, vault_root: Path):
    mock_root.return_value = vault_root
    from scripts import fam_today
    from scripts.lib import person

    rows = fam_today.compute_rows(
        today=date(2026, 5, 15),
        include_below_threshold=False,
        include_snoozed=True,
    )
    eve = next(row for row in rows if row.name == "Eve")
    assert eve.snoozed
    assert eve.score == pytest.approx(0.466666667)
    assert eve.days_overdue == 14

    def reject_constant(value):
        pytest.fail(f"nonstandard JSON constant: {value}")

    data = json.loads(
        json.dumps(fam_today.rows_as_dicts(rows), allow_nan=False), parse_constant=reject_constant
    )
    assert next(row for row in data if row["name"] == "Eve")["snoozed"]
    assert person.load(vault_root / "People" / "@Eve.md").snooze_until == date(2030, 1, 1)


@patch("scripts.lib.vault.get_vault_root")
def test_today_rejects_invalid_dates_without_writing(mock_root, vault_root: Path):
    mock_root.return_value = vault_root
    bad = vault_root / "People" / "@Invalid.md"
    bad.write_text("---\ncircle: close\nsnooze_until: tomorrow\n---\n")
    before = {p: p.read_bytes() for p in vault_root.rglob("*.md")}
    from scripts import fam_today
    from scripts.lib import validate

    with pytest.raises(validate.ValidationError, match="snooze_until"):
        fam_today.compute_rows(today=date(2026, 5, 15), include_below_threshold=True)

    assert {p: p.read_bytes() for p in vault_root.rglob("*.md")} == before


@pytest.mark.parametrize(
    "limit,expected", [(None, ["Bob", "Alice", "Dan"]), (0, []), (3, ["Bob", "Alice", "Dan"])]
)
def test_today_falls_back_to_highest_ranked_eligible_people(
    vault_root: Path, monkeypatch, capsys, limit, expected
):
    from scripts.cli import main

    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault_root))
    for name in ("Alice", "Bob", "Dan"):
        path = vault_root / f"People/@{name}.md"
        text = path.read_text()
        start = text.index("## Logged contacts")
        end = text.index("## Other references")
        path.write_text(text[:start] + "## Logged contacts\n- 2026-05-14 — call\n\n" + text[end:])
    before = {p: p.read_bytes() for p in vault_root.rglob("*.md")}
    arguments = ["today", "--on-date", "2026-05-15", "--json"]
    if limit is not None:
        arguments.extend(["--limit", str(limit)])
    assert main(arguments) == 0
    rows = json.loads(capsys.readouterr().out)["contacts"]
    assert [row["name"] for row in rows] == expected
    if rows:
        assert rows[0]["score"] == pytest.approx(-6 / 7)
        assert rows[0]["days_overdue"] == -6
    assert {p: p.read_bytes() for p in vault_root.rglob("*.md")} == before


@pytest.mark.parametrize(
    "options,expected_count",
    [([], 10), (["--limit", "3"], 3), (["--limit", "12"], 12), (["--all"], 12)],
)
def test_today_fallback_defaults_to_ten(
    vault_root: Path, monkeypatch, capsys, options, expected_count
):
    from scripts.cli import main

    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault_root))
    for number in range(11):
        (vault_root / f"People/@Suggestion {number}.md").write_text(
            "---\ncircle: close\n---\n\n## Logged contacts\n- 2026-05-14 — call\n"
        )
    assert main(["today", "--on-date", "2026-05-15", "--circle", "close", "--json", *options]) == 0
    rows = json.loads(capsys.readouterr().out)["contacts"]
    assert len(rows) == expected_count
    assert rows[0]["name"] == "Alice"
    assert all(row["score"] < 0 for row in rows)


def test_today_explains_empty_table(vault_root: Path, monkeypatch, capsys):
    from scripts.cli import main

    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault_root))
    assert main(["today", "--circle", "passive"]) == 0
    assert "No eligible contacts match this queue" in capsys.readouterr().out
