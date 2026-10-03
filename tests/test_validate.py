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


def test_validation_rejects_invalid_cadence(vault_root: Path):
    path = vault_root / "fam-circles.md"
    path.write_text(path.read_text().replace("cadence_days: 30", "cadence_days: weekly"))
    report = validate.preflight(vault_root)
    assert not report.ok
    assert any("cadence_days" in error for error in report.errors)


def test_validation_rejects_unconfigured_person_circle(vault_root: Path):
    path = vault_root / "fam-circles.md"
    path.write_text(
        "\n".join(line for line in path.read_text().splitlines() if "close:" not in line)
    )
    report = validate.preflight(vault_root)
    assert not report.ok
    assert any("@Alice.md" in error and "close" in error for error in report.errors)


@pytest.mark.parametrize(
    "bullet",
    [
        "- 2026-02-30 — impossible date",
        "- yesterday — no ISO date",
        "- 2026-05-01 no separator",
    ],
)
def test_validation_reports_malformed_logged_contacts(vault_root: Path, bullet: str):
    path = vault_root / "People" / "@Dan.md"
    path.write_text("---\ncircle: orbit\n---\n\n## Logged contacts\n" + bullet + "\n")
    report = validate.preflight(vault_root)
    assert not report.ok
    assert any(
        "@Dan.md" in error and "malformed logged contact" in error for error in report.errors
    )


def test_validation_reports_malformed_frontmatter(vault_root: Path):
    (vault_root / "People" / "@Dan.md").write_text("---\ncircle: [broken\n---\n")
    report = validate.preflight(vault_root)
    assert not report.ok
    assert any("@Dan.md" in error for error in report.errors)


def test_guard_reports_postflight_errors(vault_root: Path):
    with pytest.raises(validate.ValidationError, match="postflight failed"):
        with validate.guard(vault_root):
            (vault_root / "People" / "@New.md").write_text("---\ncircle: nonsense\n---\n")
