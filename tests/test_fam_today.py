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
    row = payload[0]
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

    rows = fam_today.compute_rows(today=date(2026, 5, 15), include_below_threshold=False)
    assert any(r.name == "Greta" for r in rows)


@patch("scripts.lib.vault.get_vault_root")
def test_today_sets_missing_circle_to_reference_and_uses_circle_queue_rules(
    mock_root, vault_root: Path
) -> None:
    mock_root.return_value = vault_root
    missing_circle = vault_root / "People" / "@Greta.md"
    missing_circle.write_text("---\nprofession: dev\n---\n\n## Logged contacts\n")

    from scripts import fam_today

    rows = fam_today.compute_rows(today=date(2026, 5, 15), include_below_threshold=True)

    assert all(r.name != "Greta" for r in rows)
    text = missing_circle.read_text()
    assert "circle: reference" in text
    assert "profession: dev" in text


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

    data = json.loads(fam_today._format_json(rows), parse_constant=reject_constant)
    assert next(row for row in data if row["name"] == "Eve")["snoozed"]
    assert person.load(vault_root / "People" / "@Eve.md").snooze_until == date(2030, 1, 1)


@patch("scripts.lib.vault.get_vault_root")
def test_today_validates_before_repairing_missing_circles(mock_root, vault_root: Path):
    mock_root.return_value = vault_root
    bad = vault_root / "People" / "@Invalid.md"
    bad.write_text("---\nsnooze_until: tomorrow\n---\n")
    before = {p: p.read_bytes() for p in vault_root.rglob("*.md")}
    from scripts import fam_today
    from scripts.lib import validate

    with pytest.raises(validate.ValidationError, match="snooze_until"):
        fam_today.compute_rows(today=date(2026, 5, 15), include_below_threshold=True)

    assert {p: p.read_bytes() for p in vault_root.rglob("*.md")} == before
