from __future__ import annotations

from pathlib import Path

import pytest

from scripts.lib import validate


def test_preflight_passes_on_fixture(vault_root: Path) -> None:
    report = validate.preflight(vault_root)
    assert report.ok, report.errors


def test_preflight_fails_when_config_missing(tmp_path: Path) -> None:
    report = validate.preflight(tmp_path)
    assert not report.ok
    assert any("fam-circles.md" in e for e in report.errors)


def test_preflight_flags_bad_person(vault_root: Path) -> None:
    bad = vault_root / "People" / "@BadPerson.md"
    bad.write_text("---\ncircle: nonsense\n---\n")
    report = validate.preflight(vault_root)
    assert not report.ok
    assert any("nonsense" in e for e in report.errors)


def test_guard_yields_when_clean(vault_root: Path) -> None:
    with validate.guard(vault_root):
        pass


def test_guard_raises_when_dirty(tmp_path: Path) -> None:
    with pytest.raises(validate.ValidationError):
        with validate.guard(tmp_path):
            pass
