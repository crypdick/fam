from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.lib import vault


def _completed(
    stdout: str = "", stderr: str = "", returncode: int = 0
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(
        args=[],
        returncode=returncode,
        stdout=stdout.encode(),
        stderr=stderr.encode(),
    )


@patch("scripts.lib.vault.subprocess.run")
def test_call_returns_stdout(mock_run: MagicMock) -> None:
    mock_run.return_value = _completed(stdout="1.12.7\n")
    out = vault.call(["version"])
    assert out == "1.12.7\n"


@patch("scripts.lib.vault.subprocess.run")
def test_call_raises_on_nonzero(mock_run: MagicMock) -> None:
    mock_run.return_value = _completed(stderr="Vault not found\n", returncode=1)
    with pytest.raises(vault.ObsidianCliError) as exc:
        vault.call(["vaults"])
    assert "Vault not found" in str(exc.value)


@patch("scripts.lib.vault.subprocess.run")
def test_call_injects_vault_name_from_env(
    mock_run: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAM_VAULT_NAME", "my-vault")
    mock_run.return_value = _completed()
    vault.call(["vault", "info=path"])
    args = mock_run.call_args.args[0]
    assert "vault=my-vault" in args


@patch("scripts.lib.vault.subprocess.run")
def test_call_omits_vault_when_env_unset(
    mock_run: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FAM_VAULT_NAME", raising=False)
    mock_run.return_value = _completed()
    vault.call(["vault", "info=path"])
    args = mock_run.call_args.args[0]
    assert not any(a.startswith("vault=") for a in args)


@patch("scripts.lib.vault.subprocess.run")
@patch(
    "scripts.lib.vault.MACOS_OBSIDIAN_CLI",
    Path("/Applications/Obsidian.app/Contents/MacOS/Obsidian"),
)
@patch("scripts.lib.vault.Path.is_file")
@patch("scripts.lib.vault.shutil.which")
def test_call_uses_macos_obsidian_app_binary_when_obsidian_not_on_path(
    mock_which: MagicMock,
    mock_is_file: MagicMock,
    mock_run: MagicMock,
) -> None:
    mock_which.return_value = None
    mock_is_file.return_value = True
    mock_run.return_value = _completed(stdout="ok\n")
    vault.call(["version"])
    args = mock_run.call_args.args[0]
    assert args[:2] == ["/Applications/Obsidian.app/Contents/MacOS/Obsidian", "version"]


@patch("scripts.lib.vault.call")
def test_get_vault_root_strips_whitespace(mock_call: MagicMock) -> None:
    mock_call.return_value = "/home/user/Documents/MyVault\n"
    assert vault.get_vault_root() == Path("/home/user/Documents/MyVault")


@patch("scripts.lib.vault.call")
def test_get_vault_root_ignores_obsidian_cli_stdout_warnings(mock_call: MagicMock) -> None:
    mock_call.return_value = (
        "2026-05-04 20:52:39 Loading updated app package "
        "/Users/ricardo/Library/Application Support/obsidian/obsidian-1.12.7.asar\n"
        "Your Obsidian installer is out of date. Please download the latest installer "
        "which includes better CLI support: https://obsidian.md/download\n"
        "/Users/ricardo/Documents/obsidian\n"
    )
    assert vault.get_vault_root() == Path("/Users/ricardo/Documents/obsidian")


@patch("scripts.lib.vault.call")
def test_backlinks_returns_paths(mock_call: MagicMock) -> None:
    mock_call.return_value = "Meetings/2026-04-01-meeting-with-alice.md\nNotes/random.md\n"
    result = vault.backlinks(Path("People/@Alice.md"))
    assert result == [
        Path("Meetings/2026-04-01-meeting-with-alice.md"),
        Path("Notes/random.md"),
    ]


@patch("scripts.lib.vault.call")
def test_backlinks_filters_no_results_sentinel(mock_call: MagicMock) -> None:
    """Regression: CLI emits `"No backlinks found."` on stdout (exit 0) when
    the target has zero backlinks. The pre-fix parser turned that line into
    `Path("No backlinks found.")` and propagated it as a fake wikilink
    (observed leaking into person notes as `[[No backlinks found.]]` —
    TODO: summarize bullets)."""
    mock_call.return_value = "No backlinks found.\n"
    assert vault.backlinks(Path("People/@Ghost.md")) == []


@patch("scripts.lib.vault.call")
def test_backlinks_filters_file_not_found_sentinel(mock_call: MagicMock) -> None:
    """CLI emits `Error: File "..." not found.` on stdout (exit 0) when the
    target path doesn't exist on disk. Same family of bug as the no-results
    sentinel — must not be parsed as a backlink path."""
    mock_call.return_value = 'Error: File "People/@Missing.md" not found.\n'
    assert vault.backlinks(Path("People/@Missing.md")) == []


@patch("scripts.lib.vault.call")
def test_backlinks_filters_mixed_sentinel_and_real(mock_call: MagicMock) -> None:
    """Defensive: even if the CLI ever interleaves a sentinel with real
    paths, only the real .md paths should survive."""
    mock_call.return_value = "Notes/a.md\nNo backlinks found.\nMeetings/b.md\n"
    assert vault.backlinks(Path("People/@X.md")) == [
        Path("Notes/a.md"),
        Path("Meetings/b.md"),
    ]


@patch("scripts.lib.vault.call")
def test_create_from_template_returns_one_when_file_appears_immediately(
    mock_call: MagicMock, tmp_path: Path
) -> None:
    """First-attempt success: file already on disk when poll runs."""
    target = tmp_path / "People" / "@X.md"
    target.parent.mkdir()
    target.write_text("")  # simulate Templater wrote it before poll
    attempts = vault.create_from_template(
        template=Path("T.md"), file=Path("People/@X.md"), vault_root=tmp_path
    )
    assert attempts == 1
    assert mock_call.call_count == 1


@patch("scripts.lib.vault.call")
def test_create_from_template_retries_when_file_missing(
    mock_call: MagicMock, tmp_path: Path
) -> None:
    """If poll times out, the wrapper re-issues the create."""
    target = tmp_path / "People" / "@X.md"
    target.parent.mkdir()
    call_count = {"n": 0}
    def _create_on_second(args: list[str]) -> str:
        call_count["n"] += 1
        if call_count["n"] == 2:
            target.write_text("")  # appears on retry
        return ""
    mock_call.side_effect = _create_on_second
    attempts = vault.create_from_template(
        template=Path("T.md"),
        file=Path("People/@X.md"),
        vault_root=tmp_path,
        poll_timeout_s=0.1,
        poll_interval_s=0.05,
    )
    assert attempts == 2
    assert mock_call.call_count == 2


@patch("scripts.lib.vault.call")
def test_create_from_template_raises_after_max_attempts(
    mock_call: MagicMock, tmp_path: Path
) -> None:
    """File never appears → raise ObsidianCliError after max_attempts."""
    target_parent = tmp_path / "People"
    target_parent.mkdir()
    mock_call.return_value = ""
    with pytest.raises(vault.ObsidianCliError, match="did not materialize"):
        vault.create_from_template(
            template=Path("T.md"),
            file=Path("People/@Ghost.md"),
            vault_root=tmp_path,
            max_attempts=2,
            poll_timeout_s=0.05,
            poll_interval_s=0.025,
        )
    assert mock_call.call_count == 2
