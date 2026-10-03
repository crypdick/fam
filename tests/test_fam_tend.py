from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest


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
@patch("scripts.lib.vault.backlinks", return_value=[Path("Meetings/2026-05-14-new.md")])
@patch("scripts.lib.vault.create_from_template", return_value=1)
def test_dry_run_previews_all_passes_without_writes(
    mock_create, _bk, mock_root, vault_root: Path, capsys
) -> None:
    mock_root.return_value = vault_root
    (vault_root / "Notes" / "new.md").write_text("[[@New Person]]\n")
    (vault_root / "People" / "index.md").write_text("# People\n")
    before = {p: p.read_bytes() for p in vault_root.rglob("*.md")}
    from scripts import fam_tend

    assert fam_tend.main(["--dry-run"]) == 0

    assert {p: p.read_bytes() for p in vault_root.rglob("*.md")} == before
    mock_create.assert_not_called()
    output = capsys.readouterr().out
    assert "would create stub: @New Person" in output
    assert "would index: People/@Alice" in output
    assert "- 2026-05-14 — meeting: [[Meetings/2026-05-14-new]]" in output


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", side_effect=_backlinks_for)
def test_tend_alice_adds_dated_bullet_idempotent(_bk, mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    from scripts import fam_tend

    fam_tend.tend(person_name="Alice")
    fam_tend.tend(person_name="Alice")  # idempotent
    text = (vault_root / "People" / "@Alice.md").read_text()
    # The fixture already had the alice meeting bullet, so no second copy
    assert text.count("[[Meetings/2026-04-01-meeting-with-alice]]") == 1


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", side_effect=_backlinks_for)
def test_tend_bob_adds_meeting_and_other_reference(_bk, mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    from scripts import fam_tend

    fam_tend.tend(person_name="Bob")
    text = (vault_root / "People" / "@Bob.md").read_text()
    assert "## Logged contacts" in text
    assert "[[Meetings/2026-04-15-team-sync]]" in text
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
    assert "[[Notes/x]]" in text
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
    assert "## Other references\n- [[Notes/x]]" in text
    assert "## Other references- " not in text


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[Path("People/index.md")])
def test_tend_dedups_against_path_prefixed_wikilink(_bk, mock_root, vault_root: Path) -> None:
    """Existing full-path links with aliases and headings prevent duplicates."""
    mock_root.return_value = vault_root
    dan = vault_root / "People" / "@Dan.md"
    dan.write_text(
        "---\ncircle: orbit\n---\n\n"
        "## Logged contacts\n\n"
        "## Other references\n"
        "- [[People/index#People|Index]] — Listed in the People index as a contact.\n"
    )
    from scripts import fam_tend

    fam_tend.tend(person_name="Dan")
    text = dan.read_text()
    assert text.count("[[index]]") == 0
    assert text.count("People/index#People|Index]]") == 1
    assert "TODO: summarize" not in text


@patch("scripts.lib.vault.get_vault_root")
@patch(
    "scripts.lib.vault.backlinks",
    return_value=[
        Path("Notes/dup.md"),
        Path("Notes/dup.md"),
    ],
)
def test_tend_dedups_duplicate_backlinks_within_run(_bk, mock_root, vault_root: Path) -> None:
    """Same backlink appearing twice in one run should be added only once."""
    mock_root.return_value = vault_root
    from scripts import fam_tend

    fam_tend.tend(person_name="Dan")
    text = (vault_root / "People" / "@Dan.md").read_text()
    assert text.count("[[Notes/dup]]") == 1


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
@patch("scripts.lib.vault.backlinks", return_value=[])
@patch("scripts.lib.vault.create_from_template", return_value=1)
def test_tend_creates_stub_for_unresolved_at_link(
    mock_create, _bk, mock_root, vault_root: Path
) -> None:
    """Gardener invokes Templater for each unresolved `[[@Name]]` mention."""
    mock_root.return_value = vault_root
    note = vault_root / "Notes" / "mentions.md"
    note.write_text("Met [[@Stub Person]] at the party.\n")
    from scripts import fam_tend

    stubs = fam_tend.tend().stubs
    assert "@Stub Person" in stubs.created
    assert "@Stub Person" not in stubs.retried
    mock_create.assert_called_once()
    kwargs = mock_create.call_args.kwargs
    assert kwargs["template"] == Path("Templates/person_template.md")
    assert kwargs["file"] == Path("People/@Stub Person.md")
    assert kwargs["vault_root"] == vault_root


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[])
@patch("scripts.lib.vault.create_from_template", return_value=2)
def test_tend_records_retry_when_create_needed_extra_attempt(
    _create, _bk, mock_root, vault_root: Path
) -> None:
    """Stubs that needed more than one Templater attempt show up in `retried`."""
    mock_root.return_value = vault_root
    note = vault_root / "Notes" / "mentions.md"
    note.write_text("Met [[@Flaky Stub]] today.\n")
    from scripts import fam_tend

    stubs = fam_tend.tend().stubs
    assert "@Flaky Stub" in stubs.created
    assert "@Flaky Stub" in stubs.retried


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[])
def test_tend_records_failed_stub_when_retries_exhausted(_bk, mock_root, vault_root: Path) -> None:
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
        stubs = fam_tend.tend().stubs
    assert "@Easy Win" in stubs.created
    assert "@Hard Fail" not in stubs.created
    assert any("@Hard Fail" in f for f in stubs.failed)


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

    stubs = fam_tend.tend().stubs
    assert "@Alice" not in stubs.created
    for call in mock_create.call_args_list:
        assert call.kwargs["file"] != Path("People/@Alice.md")


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[])
@patch("scripts.lib.vault.create_from_template")
def test_tend_aborts_when_stub_config_missing(_create, _bk, mock_root, vault_root: Path) -> None:
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

    stubs = fam_tend.tend(person_name="Alice").stubs
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
@patch("scripts.lib.vault.backlinks", return_value=[])
def test_sync_appends_unlinked_persons_after_last_person_bullet(
    _bk, mock_root, vault_root: Path
) -> None:
    """New `@*.md` files in people_folder land right after the last existing
    `- [[People/@*]]` bullet, keeping the person list contiguous."""
    mock_root.return_value = vault_root
    index_md = vault_root / "People" / "index.md"
    index_md.write_text(
        "# People\n\n"
        "- [[plans/index|Plans]] — design docs\n\n"
        "- [[People/@Alice]] — contact\n"
        "- [[People/@Bob]] — contact\n"
    )
    from scripts import fam_tend

    sync = fam_tend.tend().index_sync
    text = index_md.read_text()
    assert sorted(sync.added) == ["People/@Carol", "People/@Dan", "People/@Eve"]
    last_bob = text.index("- [[People/@Bob]] — contact\n") + len("- [[People/@Bob]] — contact\n")
    next_chunk = text[last_bob : last_bob + 200]
    assert next_chunk.startswith("- [[People/@Carol]] — contact\n")
    assert "[[plans/index|Plans]]" in text  # meta section preserved


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[])
def test_sync_eof_fallback_when_no_existing_person_bullets(
    _bk, mock_root, vault_root: Path
) -> None:
    """Index without any `- [[People/@*]]` bullets gets new entries at EOF."""
    mock_root.return_value = vault_root
    index_md = vault_root / "People" / "index.md"
    index_md.write_text("# People\n\nNo bullets yet.\n")
    from scripts import fam_tend

    sync = fam_tend.tend().index_sync
    assert len(sync.added) == 5
    text = index_md.read_text()
    assert text.endswith("- [[People/@Eve]] — contact\n")
    assert text.startswith("# People\n\nNo bullets yet.\n")


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[])
def test_sync_skipped_when_index_missing(_bk, mock_root, vault_root: Path) -> None:
    """No `<people_folder>/index.md` → skip silently, do not create one."""
    mock_root.return_value = vault_root
    assert not (vault_root / "People" / "index.md").exists()
    from scripts import fam_tend

    sync = fam_tend.tend().index_sync
    assert sync.added == []
    assert sync.skipped_reason == "index.md missing"
    assert not (vault_root / "People" / "index.md").exists()


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[])
def test_sync_is_idempotent(_bk, mock_root, vault_root: Path) -> None:
    """Running tend twice yields no duplicate index entries."""
    mock_root.return_value = vault_root
    index_md = vault_root / "People" / "index.md"
    index_md.write_text("# People\n\n- [[People/@Alice]] — contact\n")
    from scripts import fam_tend

    fam_tend.tend()
    fam_tend.tend()
    text = index_md.read_text()
    for name in ("@Alice", "@Bob", "@Carol", "@Dan", "@Eve"):
        assert text.count(f"[[People/{name}]]") == 1


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[])
def test_sync_skipped_when_person_filter_set(_bk, mock_root, vault_root: Path) -> None:
    """`--person <name>` is single-target work; whole-vault index sync skipped."""
    mock_root.return_value = vault_root
    index_md = vault_root / "People" / "index.md"
    index_md.write_text("# People\n")
    from scripts import fam_tend

    sync = fam_tend.tend(person_name="Alice").index_sync
    assert sync.added == []
    assert sync.skipped_reason == "--person filter set"
    assert index_md.read_text() == "# People\n"


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[])
def test_sync_dedups_against_path_prefixed_wikilinks(_bk, mock_root, vault_root: Path) -> None:
    """Entries linked as `[[People/@Alice]]` count as already-indexed."""
    mock_root.return_value = vault_root
    index_md = vault_root / "People" / "index.md"
    index_md.write_text("# People\n\n- [[People/@Alice|Alice]] — contact\n")
    from scripts import fam_tend

    sync = fam_tend.tend().index_sync
    assert "People/@Alice" not in sync.added
    assert sorted(sync.added) == ["People/@Bob", "People/@Carol", "People/@Dan", "People/@Eve"]


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[])
def test_sync_ignores_syncthing_conflict_person_copies(_bk, mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    conflict = vault_root / "People" / "@Zed.sync-conflict-20260523-225211-I3CHISF.md"
    conflict.write_text("---\ncircle: close\n---\n")
    index_md = vault_root / "People" / "index.md"
    index_md.write_text("# People\n\n- [[People/@Alice]] — contact\n")

    from scripts import fam_tend

    run = fam_tend.tend()
    text = index_md.read_text()

    assert "@Zed.sync-conflict" not in run.index_sync.added
    assert "@Zed.sync-conflict" not in text
    assert "Zed.sync-conflict" not in {r.person for r in run.results}


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks")
def test_tend_aborts_before_writes_on_invalid_person(
    mock_backlinks, mock_root, vault_root: Path
) -> None:
    mock_root.return_value = vault_root
    (vault_root / "People" / "@Broken.md").write_text("---\ncircle: nonsense\n---\n")
    before = {p: p.read_bytes() for p in vault_root.rglob("*.md")}
    from scripts import fam_tend
    from scripts.lib import validate

    with pytest.raises(validate.ValidationError, match="preflight failed"):
        fam_tend.tend()

    assert {p: p.read_bytes() for p in vault_root.rglob("*.md")} == before
    mock_backlinks.assert_not_called()


@patch("scripts.lib.vault.get_vault_root")
def test_tend_main_reports_validation_failure(mock_root, vault_root: Path, capsys) -> None:
    mock_root.return_value = vault_root
    (vault_root / "People" / "@Broken.md").write_text("---\ncircle: nonsense\n---\n")
    from scripts import fam_tend

    assert fam_tend.main([]) == 1
    assert "preflight failed" in capsys.readouterr().err


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[])
def test_tend_rejects_invalid_materialized_stub(_bk, mock_root, vault_root: Path) -> None:
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
@patch("scripts.lib.vault.backlinks", return_value=[])
def test_tend_main_fails_when_stub_creation_fails(_bk, mock_root, vault_root: Path, capsys):
    mock_root.return_value = vault_root
    (vault_root / "Notes" / "new.md").write_text("[[@New Person]]\n")
    from scripts import fam_tend
    from scripts.lib import vault

    with patch(
        "scripts.lib.vault.create_from_template", side_effect=vault.ObsidianCliError("failed")
    ):
        assert fam_tend.main([]) == 1
    assert "failed stub creation" in capsys.readouterr().err


@pytest.mark.parametrize(
    "mention",
    [
        "Add `## Logged contacts` later.\n",
        "```md\n## Logged contacts\n```\n",
        "~~~md\n## Logged contacts\n~~~\n",
    ],
)
@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[Path("Meetings/2026-05-14-new.md")])
def test_tend_ignores_heading_examples(_bk, mock_root, mention, vault_root: Path):
    mock_root.return_value = vault_root
    note = vault_root / "People" / "@Dan.md"
    note.write_text("---\ncircle: orbit\n---\n\n" + mention + "\n## Other references\n")
    from scripts import fam_tend
    from scripts.lib import interactions, person

    fam_tend.tend(person_name="Dan")

    assert interactions.last_contacted(person.load(note)) == date(2026, 5, 14)
    assert mention.strip() in note.read_text()
    assert note.read_text().count("\n## Logged contacts\n") == 1 + mention.count(
        "\n## Logged contacts\n"
    )


@patch("scripts.lib.vault.get_vault_root")
@patch(
    "scripts.lib.vault.backlinks",
    return_value=[
        Path("Work/2026-05-14-meeting.md"),
        Path("Social/2026-05-14-meeting.md"),
    ],
)
def test_tend_keeps_distinct_backlink_paths(_bk, mock_root, vault_root: Path):
    mock_root.return_value = vault_root
    from scripts import fam_tend

    fam_tend.tend(person_name="Dan")
    fam_tend.tend(person_name="Dan")

    text = (vault_root / "People" / "@Dan.md").read_text()
    assert text.count("[[Work/2026-05-14-meeting]]") == 1
    assert text.count("[[Social/2026-05-14-meeting]]") == 1


@patch("scripts.lib.vault.get_vault_root")
@patch("scripts.lib.vault.backlinks", return_value=[])
def test_tend_does_not_rewrite_unchanged_notes(_bk, mock_root, vault_root: Path):
    mock_root.return_value = vault_root
    eve = vault_root / "People" / "@Eve.md"
    eve.write_text(eve.read_text() + "\n## Other references\n")
    before = {p: p.read_bytes() for p in vault_root.rglob("*.md")}
    from scripts import fam_tend

    fam_tend.tend()

    assert {p: p.read_bytes() for p in vault_root.rglob("*.md")} == before
