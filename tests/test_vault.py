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


@patch("scripts.lib.vault.call")
def test_get_vault_root_strips_whitespace(mock_call: MagicMock) -> None:
    mock_call.return_value = "/home/user/Documents/MyVault\n"
    assert vault.get_vault_root() == Path("/home/user/Documents/MyVault")


@patch("scripts.lib.vault.call")
def test_backlinks_returns_paths(mock_call: MagicMock) -> None:
    mock_call.return_value = "Meetings/2026-04-01-meeting-with-alice.md\nNotes/random.md\n"
    result = vault.backlinks(Path("People/@Alice.md"))
    assert result == [
        Path("Meetings/2026-04-01-meeting-with-alice.md"),
        Path("Notes/random.md"),
    ]
