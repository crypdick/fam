from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch


def _backlinks_for(target: Path) -> list[Path]:
    name = target.stem  # e.g. "@Alice"
    if name == "@Alice":
        return [Path("Meetings/2026-04-01-meeting-with-alice.md")]
    if name == "@Bob":
        return [
            Path("Meetings/2026-04-15-team-sync.md"),
            Path("Notes/random-note-mentioning-bob.md"),
        ]
    return []


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", side_effect=_backlinks_for)
def test_tend_alice_adds_dated_bullet_idempotent(_bk, mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    from scripts import fam_tend
    fam_tend.tend(person_name="Alice")
    fam_tend.tend(person_name="Alice")  # idempotent
    text = (vault_root / "People" / "@Alice.md").read_text()
    # The fixture already had the alice meeting bullet, so no second copy
    assert text.count("[[2026-04-01-meeting-with-alice]]") == 1


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", side_effect=_backlinks_for)
def test_tend_bob_adds_meeting_and_other_reference(_bk, mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    from scripts import fam_tend
    fam_tend.tend(person_name="Bob")
    text = (vault_root / "People" / "@Bob.md").read_text()
    assert "## Logged contacts" in text
    assert "[[2026-04-15-team-sync]]" in text
    assert "## Other references" in text
    # Other-reference bullet was pre-seeded; gardener should not duplicate.
    assert text.count("random-note-mentioning-bob") == 1


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[Path("Notes/x.md")])
def test_tend_writes_todo_placeholder_for_unknown_summary(_bk, mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    from scripts import fam_tend
    fam_tend.tend(person_name="Dan")
    text = (vault_root / "People" / "@Dan.md").read_text()
    assert "[[x]]" in text
    assert "TODO: summarize" in text
