from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.call", return_value="Notes/2026-10-01-mention.md\n")
def test_tend_preserves_existing_notes_and_contact_dates(
    mock_cli, mock_root, vault_root: Path
) -> None:
    from scripts import fam_tend
    from scripts.lib import interactions, person

    mock_root.return_value = vault_root
    (vault_root / "People" / "index.md").write_text("# People\n")
    bob = vault_root / "People" / "@Bob.md"
    before = {p: p.read_bytes() for p in vault_root.rglob("*.md")}
    last_contact = interactions.last_contacted(person.load(bob))

    fam_tend.tend()

    assert interactions.last_contacted(person.load(bob)) == last_contact
    assert {p: p.read_bytes() for p in vault_root.rglob("*.md")} == before
    mock_cli.assert_not_called()


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.create_from_template")
def test_tend_person_creates_only_requested_note(mock_create, mock_root, vault_root: Path) -> None:
    from scripts import fam_tend

    mock_root.return_value = vault_root
    (vault_root / "Notes" / "new.md").write_text("[[@Unrelated Person]]\n")
    before = {p: p.read_bytes() for p in vault_root.rglob("*.md")}
    target = vault_root / "People" / "@New Person.md"

    def create(*, template, file, vault_root):
        assert template == Path("Templates/person_template.md")
        assert file == Path("People/@New Person.md")
        (vault_root / file).write_text("---\ncircle: passive\n---\n\n## Logged contacts\n")
        return 1

    mock_create.side_effect = create
    fam_tend.tend(person_name="New Person")

    assert target.is_file()
    assert {p: p.read_bytes() for p in before} == before
    assert not (vault_root / "People" / "@Unrelated Person.md").exists()
    mock_create.assert_called_once()


def test_scan_at_wikilinks_finds_unresolved_at_links(vault_root: Path) -> None:
    """Scanner picks up direct `@`-prefixed wikilinks vault-wide; ignores non-`@` links."""
    note = vault_root / "Notes" / "stub_mentions.md"
    note.write_text(
        "Talked about [[@NewPerson]] and [[@Alice]] today.\n"
        "Also referenced [[some-project]] and [[wiki/People/@PathPrefixed]].\n"
    )
    from scripts.fam_tend import _scan_at_wikilinks

    found = _scan_at_wikilinks(vault_root)
    assert "@NewPerson" in found
    assert "@Alice" in found
    assert "@PathPrefixed" not in found
    assert "some-project" not in found


def test_scan_at_wikilinks_ignores_code_examples_and_placeholders(vault_root: Path) -> None:
    """Incident/changelog examples should not trigger recurring Templater stub attempts."""
    note = vault_root / "Notes" / "stub_examples.md"
    note.write_text(
        "Literal placeholder `[[@Name]]` and glob `[[@*.sync-conflict-*]]`.\n"
        "```md\n[[ @Nope]]\n[[@Code Block Person]]\n```\n"
        "Namespaced target [[Z/@OpenAI]] should stay in its namespace.\n"
        "Real mention [[@Real Person]] still counts.\n"
    )
    from scripts.fam_tend import _scan_at_wikilinks

    found = _scan_at_wikilinks(vault_root)
    assert "@Real Person" in found
    assert "@Name" not in found
    assert "@*.sync-conflict-*" not in found
    assert "@Code Block Person" not in found
    assert "@OpenAI" not in found


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.create_from_template", return_value=1)
def test_tend_creates_stub_for_unresolved_at_link(mock_create, mock_root, vault_root: Path) -> None:
    """Gardener invokes Templater for each unresolved `[[@Name]]` mention."""
    mock_root.return_value = vault_root
    note = vault_root / "Notes" / "mentions.md"
    note.write_text("Met [[@Stub Person]] at the party.\n")
    from scripts import fam_tend

    stubs = fam_tend.tend()
    assert "@Stub Person" in stubs.created
    assert "@Stub Person" not in stubs.retried
    mock_create.assert_called_once()
    kwargs = mock_create.call_args.kwargs
    assert kwargs["template"] == Path("Templates/person_template.md")
    assert kwargs["file"] == Path("People/@Stub Person.md")
    assert kwargs["vault_root"] == vault_root


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.create_from_template", return_value=2)
def test_tend_records_retry_when_create_needed_extra_attempt(
    _create, mock_root, vault_root: Path
) -> None:
    """Stubs that needed more than one Templater attempt show up in `retried`."""
    mock_root.return_value = vault_root
    note = vault_root / "Notes" / "mentions.md"
    note.write_text("Met [[@Flaky Stub]] today.\n")
    from scripts import fam_tend

    stubs = fam_tend.tend()
    assert "@Flaky Stub" in stubs.created
    assert "@Flaky Stub" in stubs.retried


@patch("scripts.lib.vault.get_vault_root")
def test_tend_records_failed_stub_when_retries_exhausted(mock_root, vault_root: Path) -> None:
    """When `create_from_template` raises after exhausting retries, the stub
    lands in `failed` and the run does not abort other stubs."""
    mock_root.return_value = vault_root
    note = vault_root / "Notes" / "mentions.md"
    note.write_text("Met [[@Hard Fail]] and [[@Easy Win]] today.\n")
    from scripts import fam_tend
    from scripts.lib import vault as vault_mod

    def _flaky(*, template, file, vault_root):
        if "Hard Fail" in file.name:
            raise vault_mod.ObsidianCliError("dropped")
        return 1

    with patch("scripts.lib.vault.create_from_template", side_effect=_flaky):
        stubs = fam_tend.tend()
    assert "@Easy Win" in stubs.created
    assert "@Hard Fail" not in stubs.created
    assert any("@Hard Fail" in f for f in stubs.failed)


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.create_from_template")
def test_tend_skips_stub_creation_when_person_already_exists(
    mock_create, mock_root, vault_root: Path
) -> None:
    """Existing `@Alice.md` (in fixture) → no stub creation for `[[@Alice]]`."""
    mock_root.return_value = vault_root
    note = vault_root / "Notes" / "alice_mention.md"
    note.write_text("Saw [[@Alice]] yesterday.\n")
    from scripts import fam_tend

    stubs = fam_tend.tend()
    assert "@Alice" not in stubs.created
    for call in mock_create.call_args_list:
        assert call.kwargs["file"] != Path("People/@Alice.md")


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.create_from_template")
def test_tend_aborts_when_stub_config_missing(_create, mock_root, vault_root: Path) -> None:
    """Unresolved [[@…]] link with no people_folder/person_template → ConfigError."""
    mock_root.return_value = vault_root
    config_path = vault_root / "fam-circles.md"
    config_path.write_text(
        "\n".join(
            line
            for line in config_path.read_text().splitlines()
            if not line.startswith(("people_folder:", "person_template:"))
        )
    )
    note = vault_root / "Notes" / "stub_mention.md"
    note.write_text("Met [[@Unconfigured Stub]] today.\n")
    from scripts import fam_tend
    from scripts.lib import config

    with pytest.raises(config.ConfigError, match="people_folder"):
        fam_tend.tend()


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.create_from_template")
def test_tend_person_leaves_existing_note_anywhere_unchanged(
    mock_create, mock_root, vault_root: Path
) -> None:
    """`--person <name>` is single-target work; whole-vault stub scan is skipped."""
    mock_root.return_value = vault_root
    (vault_root / "People" / "@Alice.md").rename(vault_root / "Notes" / "@Alice.md")
    before = (vault_root / "Notes" / "@Alice.md").read_bytes()
    note = vault_root / "Notes" / "would_create.md"
    note.write_text("Met [[@Would Be Stub]] today.\n")
    from scripts import fam_tend

    stubs = fam_tend.tend(person_name="Alice")
    assert (vault_root / "Notes" / "@Alice.md").read_bytes() == before
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


def test_scan_at_wikilinks_skips_syncthing_conflict_files(vault_root: Path) -> None:
    conflict = vault_root / "Notes" / "incident.sync-conflict-20260523-225211-I3CHISF.md"
    conflict.write_text("Mention of [[@Conflict Only Person]] in a conflict copy.\n")

    from scripts.fam_tend import _scan_at_wikilinks

    found = _scan_at_wikilinks(vault_root)

    assert "@Conflict Only Person" not in found


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.create_from_template")
def test_tend_aborts_before_writes_on_invalid_person(
    mock_create, mock_root, vault_root: Path
) -> None:
    mock_root.return_value = vault_root
    (vault_root / "People" / "@Broken.md").write_text("---\ncircle: nonsense\n---\n")
    before = {p: p.read_bytes() for p in vault_root.rglob("*.md")}
    from scripts import fam_tend
    from scripts.lib import validate

    with pytest.raises(validate.ValidationError, match="preflight failed"):
        fam_tend.tend()

    assert {p: p.read_bytes() for p in vault_root.rglob("*.md")} == before
    mock_create.assert_not_called()


@patch("scripts.lib.vault.get_vault_root")
def test_tend_main_reports_validation_failure(mock_root, vault_root: Path, capsys) -> None:
    mock_root.return_value = vault_root
    (vault_root / "People" / "@Broken.md").write_text("---\ncircle: nonsense\n---\n")
    from scripts import fam_tend

    assert fam_tend.main([]) == 1
    assert "preflight failed" in capsys.readouterr().err


@patch("scripts.lib.vault.get_vault_root")
def test_tend_rejects_invalid_materialized_stub(mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    (vault_root / "Notes" / "new.md").write_text("[[@New Person]]\n")
    from scripts import fam_tend
    from scripts.lib import validate

    def create_invalid(*, template, file, vault_root):
        (vault_root / file).write_text("---\ncircle: nonsense\n---\n")
        return 1

    with patch("scripts.lib.vault.create_from_template", side_effect=create_invalid):
        with pytest.raises(validate.ValidationError, match="unknown circle"):
            fam_tend.tend()


@patch("scripts.lib.vault.get_vault_root")
def test_tend_main_fails_when_stub_creation_fails(mock_root, vault_root: Path, capsys):
    mock_root.return_value = vault_root
    (vault_root / "Notes" / "new.md").write_text("[[@New Person]]\n")
    from scripts import fam_tend
    from scripts.lib import vault

    with patch(
        "scripts.lib.vault.create_from_template", side_effect=vault.ObsidianCliError("failed")
    ):
        assert fam_tend.main([]) == 1
    assert "failed stub creation" in capsys.readouterr().err


@pytest.mark.parametrize("args", [[], ["--person", "@New Person"]])
@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.create_from_template")
def test_dry_run_previews_creation_without_writes(
    mock_create, mock_root, vault_root: Path, capsys, args
) -> None:
    from scripts import fam_tend

    mock_root.return_value = vault_root
    (vault_root / "Notes" / "new.md").write_text("[[@New Person]]\n")
    (vault_root / "People" / "index.md").write_text("# People\n")
    before = {p: p.read_bytes() for p in vault_root.rglob("*.md")}

    assert fam_tend.main(["--dry-run", *args]) == 0

    assert {p: p.read_bytes() for p in vault_root.rglob("*.md")} == before
    mock_create.assert_not_called()
    assert capsys.readouterr().out == "would create stub: @New Person\n"


@pytest.mark.parametrize("name", ["", "@", "../Escape", "Folder/Name", "Name|Alias", "Na\nme"])
@patch("scripts.lib.vault.get_vault_root")
def test_person_rejects_invalid_names(mock_root, name: str, capsys) -> None:
    from scripts import fam_tend

    assert fam_tend.main(["--person", name]) == 1
    assert "--person must be a person name" in capsys.readouterr().err
    mock_root.assert_not_called()


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.create_from_template")
def test_created_stub_is_not_recreated(mock_create, mock_root, vault_root: Path) -> None:
    from scripts import fam_tend

    mock_root.return_value = vault_root
    (vault_root / "Notes" / "new.md").write_text("[[@New Person]]\n")

    def create(*, template, file, vault_root):
        (vault_root / file).write_text("---\ncircle: passive\n---\n")
        return 1

    mock_create.side_effect = create
    assert fam_tend.tend().created == ["@New Person"]
    assert fam_tend.tend().created == []
    mock_create.assert_called_once()
