from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch


@patch("scripts.lib.vault.get_vault_root")
def test_today_default_includes_overdue(mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    from scripts import fam_today
    rows = fam_today.compute_rows(today=date(2026, 5, 15), include_below_threshold=False)
    names = {r.name for r in rows}
    assert "Bob" in names      # inner cadence 7, last 2026-04-25 → overdue
    assert "Carol" not in names  # passive
    assert "Dan" in names       # never contacted → +inf


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
    assert (
        {"name", "circle", "last_contacted", "days", "days_overdue", "score", "path"} <= row.keys()
    )


@patch("scripts.lib.vault.get_vault_root")
def test_today_table_includes_days_overdue_column(mock_root, vault_root: Path, capsys) -> None:
    mock_root.return_value = vault_root
    from scripts import fam_today
    fam_today.run(today=date(2026, 5, 15), json_out=False)
    captured = capsys.readouterr()
    assert "DAYS_OVERDUE" in captured.out
