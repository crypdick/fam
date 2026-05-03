from __future__ import annotations

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


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[Path("Notes/x.md")])
def test_tend_keeps_heading_on_its_own_line(_bk, mock_root, vault_root: Path) -> None:
    """Regression: when a person note ends with `## Other references` and no
    trailing newline, the inserted bullet must not concatenate onto the
    heading line (`## Other references- [[x]] — TODO: summarize`).
    """
    mock_root.return_value = vault_root
    from scripts import fam_tend
    fam_tend.tend(person_name="Dan")
    text = (vault_root / "People" / "@Dan.md").read_text()
    assert "## Other references\n- [[x]]" in text
    assert "## Other references- " not in text


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[Path("People/index.md")])
def test_tend_dedups_against_path_prefixed_wikilink(_bk, mock_root, vault_root: Path) -> None:
    """Regression: when Obsidian's link-update linter expands `[[index]]` to
    `[[wiki/People/index]]` between tend runs, the next run must still
    recognize the entry and not re-add `[[index]] — TODO: summarize`.
    """
    dan = vault_root / "People" / "@Dan.md"
    dan.write_text(
        "---\ncircle: orbit\n---\n\n"
        "## Logged contacts\n\n"
        "## Other references\n"
        "- [[wiki/People/index]] — Listed in the People index as a contact.\n"
    )
    from scripts import fam_tend
    fam_tend.tend(person_name="Dan")
    text = dan.read_text()
    assert text.count("[[index]]") == 0
    assert text.count("People/index]]") == 1
    assert "TODO: summarize" not in text


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[Path("Notes/legacy.md")])
def test_tend_dedups_across_sections(_bk, mock_root, vault_root: Path) -> None:
    """Regression: a non-meeting backlink that an older tend version routed
    into `## Logged contacts` must not be re-added under `## Other references`
    on a current run. Skip if the link is already anywhere in the body.
    """
    dan = vault_root / "People" / "@Dan.md"
    dan.write_text(
        "---\ncircle: orbit\n---\n\n"
        "## Logged contacts\n"
        "- [[legacy]] — TODO: summarize\n\n"
        "## Other references\n"
    )
    from scripts import fam_tend
    fam_tend.tend(person_name="Dan")
    text = dan.read_text()
    assert text.count("[[legacy]]") == 1


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[
    Path("Notes/dup.md"), Path("Notes/dup.md"),
])
def test_tend_dedups_duplicate_backlinks_within_run(_bk, mock_root, vault_root: Path) -> None:
    """Same backlink appearing twice in one run should be added only once."""
    mock_root.return_value = vault_root
    from scripts import fam_tend
    fam_tend.tend(person_name="Dan")
    text = (vault_root / "People" / "@Dan.md").read_text()
    assert text.count("[[dup]]") == 1


def test_wikilink_basename_normalization() -> None:
    from scripts.fam_tend import _wikilink_basename
    assert _wikilink_basename("index") == "index"
    assert _wikilink_basename("wiki/People/index") == "index"
    assert _wikilink_basename("wiki/People/index.md") == "index"
    assert _wikilink_basename("index|People") == "index"
    assert _wikilink_basename("index#Section") == "index"
    assert _wikilink_basename("wiki/People/index#Section|alias") == "index"
