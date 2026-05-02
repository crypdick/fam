from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


@patch("scripts.lib.vault.get_vault_root")
def test_returns_zero_on_clean_fixture(mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    from scripts import fam_validate
    code = fam_validate.main()
    assert code == 0


@patch("scripts.lib.vault.get_vault_root")
def test_returns_nonzero_on_bad_circle(mock_root, vault_root: Path) -> None:
    mock_root.return_value = vault_root
    bad = vault_root / "People" / "@BadPerson.md"
    bad.write_text("---\ncircle: nonsense\n---\n")
    from scripts import fam_validate
    code = fam_validate.main()
    assert code != 0
