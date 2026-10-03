from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


@patch("scripts.lib.vault.get_vault_root")
def test_returns_zero_on_clean_fixture(mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    from scripts import fam_validate

    code = fam_validate.main([])
    assert code == 0


@patch("scripts.lib.vault.get_vault_root")
def test_returns_nonzero_on_bad_circle(mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    bad = vault_root / "People" / "@BadPerson.md"
    bad.write_text("---\ncircle: nonsense\n---\n")
    from scripts import fam_validate

    code = fam_validate.main([])
    assert code != 0


@patch("scripts.lib.vault.get_vault_root")
def test_help_does_not_access_vault(mock_root, capsys):
    from scripts import fam_validate

    with pytest.raises(SystemExit) as exc:
        fam_validate.main(["--help"])
    assert exc.value.code == 0
    assert "usage: fam-validate" in capsys.readouterr().out
    mock_root.assert_not_called()
