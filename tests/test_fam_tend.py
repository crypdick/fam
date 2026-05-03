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
    mock_root.return_value = vault_root
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
    mock_root.return_value = vault_root
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


def test_scan_at_wikilinks_finds_unresolved_at_links(vault_root: Path) -> None:
    """Scanner picks up `@`-prefixed wikilinks vault-wide; ignores non-`@` links."""
    note = vault_root / "Notes" / "stub_mentions.md"
    note.write_text(
        "Talked about [[@NewPerson]] and [[@Alice]] today.\n"
        "Also referenced [[some-project]] and [[wiki/People/@PathPrefixed]].\n"
    )
    from scripts.fam_tend import _scan_at_wikilinks
    found = _scan_at_wikilinks(vault_root)
    assert "@NewPerson" in found
    assert "@Alice" in found
    assert "@PathPrefixed" in found
    assert "some-project" not in found


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[])
@patch("scripts.lib.vault.create_from_template")
def test_tend_creates_stub_for_unresolved_at_link(
    mock_create, _bk, mock_root, vault_root: Path
) -> None:
    """Gardener invokes Templater for each unresolved `[[@Name]]` mention."""
    mock_root.return_value = vault_root
    note = vault_root / "Notes" / "mentions.md"
    note.write_text("Met [[@Stub Person]] at the party.\n")
    from scripts import fam_tend
    stubs, _ = fam_tend.tend()
    assert "@Stub Person" in stubs.created
    mock_create.assert_called_once()
    kwargs = mock_create.call_args.kwargs
    assert kwargs["template"] == Path("Templates/person_template.md")
    assert kwargs["file"] == Path("People/@Stub Person.md")


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[])
@patch("scripts.lib.vault.create_from_template")
def test_tend_skips_stub_creation_when_person_already_exists(
    mock_create, _bk, mock_root, vault_root: Path
) -> None:
    """Existing `@Alice.md` (in fixture) → no stub creation for `[[@Alice]]`."""
    mock_root.return_value = vault_root
    note = vault_root / "Notes" / "alice_mention.md"
    note.write_text("Saw [[@Alice]] yesterday.\n")
    from scripts import fam_tend
    stubs, _ = fam_tend.tend()
    assert "@Alice" not in stubs.created
    for call in mock_create.call_args_list:
        assert call.kwargs["file"] != Path("People/@Alice.md")


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[])
@patch("scripts.lib.vault.create_from_template")
def test_tend_aborts_when_stub_config_missing(
    _create, _bk, mock_root, vault_root: Path
) -> None:
    """Unresolved [[@…]] link with no people_folder/person_template → ConfigError."""
    mock_root.return_value = vault_root
    (vault_root / "fam-circles.md").write_text(
        "# fam — circles\n\n```yaml\ncircles:\n"
        "  passive: {cadence_days: null, alert_threshold: null}\n```\n"
    )
    note = vault_root / "Notes" / "stub_mention.md"
    note.write_text("Met [[@Unconfigured Stub]] today.\n")
    from scripts import fam_tend
    from scripts.lib import config
    import pytest as _pytest
    with _pytest.raises(config.ConfigError, match="people_folder"):
        fam_tend.tend()


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[])
@patch("scripts.lib.vault.create_from_template")
def test_tend_skips_stub_pass_when_person_filter_set(
    mock_create, _bk, mock_root, vault_root: Path
) -> None:
    """`--person <name>` is single-target work; whole-vault stub scan is skipped."""
    mock_root.return_value = vault_root
    note = vault_root / "Notes" / "would_create.md"
    note.write_text("Met [[@Would Be Stub]] today.\n")
    from scripts import fam_tend
    stubs, _ = fam_tend.tend(person_name="Alice")
    assert stubs.created == []
    mock_create.assert_not_called()


def test_scan_at_wikilinks_skips_dotfile_dirs(vault_root: Path) -> None:
    """`.obsidian/`, `.trash/` etc. shouldn't trigger stub creation."""
    hidden = vault_root / ".obsidian" / "scratch.md"
    hidden.parent.mkdir(exist_ok=True)
    hidden.write_text("Mention of [[@Hidden Person]] in plugin scratch.\n")
    from scripts.fam_tend import _scan_at_wikilinks
    found = _scan_at_wikilinks(vault_root)
    assert "@Hidden Person" not in found
