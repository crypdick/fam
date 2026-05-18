from __future__ import annotations

import math
from pathlib import Path

import pytest

from scripts.lib import config


def test_load_parses_fixture_vault(vault_root: Path) -> None:
    cfg = config.load(vault_root)
    assert set(cfg.circles) == {"reference", "passive", "inner", "close", "orbit", "distant"}
    assert cfg.circles["inner"].cadence_days == 7
    assert cfg.circles["inner"].alert_threshold == -0.2
    assert cfg.circles["passive"].cadence_days is None
    assert cfg.circles["passive"].alert_threshold is None


def test_load_aborts_when_circles_file_missing(tmp_path: Path) -> None:
    with pytest.raises(config.ConfigError, match="fam-circles.md not found"):
        config.load(tmp_path)


def test_load_aborts_when_multiple_matches(vault_root: Path) -> None:
    extra = vault_root / "subdir" / "fam-circles.md"
    extra.parent.mkdir()
    extra.write_text((vault_root / "fam-circles.md").read_text())
    with pytest.raises(config.ConfigError, match="multiple"):
        config.load(vault_root)


def test_load_ignores_dotfile_dir_duplicates(vault_root: Path) -> None:
    """Syncthing's `.stversions/` mirrors vault contents — must not collide."""
    stversion = vault_root / ".stversions" / "fam-circles.md"
    stversion.parent.mkdir()
    stversion.write_text((vault_root / "fam-circles.md").read_text())
    cfg = config.load(vault_root)
    assert cfg.path == vault_root / "fam-circles.md"


def test_load_respects_explicit_circles_path(vault_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    nested = vault_root / "wiki" / "People" / "fam-circles.md"
    nested.parent.mkdir(parents=True)
    nested.write_text((vault_root / "fam-circles.md").read_text())
    (vault_root / "fam-circles.md").unlink()
    monkeypatch.setenv("FAM_CIRCLES_PATH", "wiki/People/fam-circles.md")

    cfg = config.load(vault_root)

    assert cfg.path == nested


def test_load_rejects_missing_explicit_circles_path(
    vault_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAM_CIRCLES_PATH", "wiki/People/fam-circles.md")

    with pytest.raises(config.ConfigError, match="FAM_CIRCLES_PATH points to missing"):
        config.load(vault_root)


def test_load_aborts_on_no_yaml_block(vault_root: Path) -> None:
    (vault_root / "fam-circles.md").write_text("# fam — circles\n\nNo yaml here.\n")
    with pytest.raises(config.ConfigError, match="no yaml"):
        config.load(vault_root)


def test_load_aborts_on_invalid_yaml(vault_root: Path) -> None:
    (vault_root / "fam-circles.md").write_text(
        "# fam — circles\n\n```yaml\ncircles: {{{ broken\n```\n"
    )
    with pytest.raises(config.ConfigError):
        config.load(vault_root)


def test_circle_config_dataclass_fields() -> None:
    c = config.CircleConfig(cadence_days=7, alert_threshold=-0.2)
    assert c.cadence_days == 7
    assert math.isclose(c.alert_threshold or 0.0, -0.2)


def test_load_parses_optional_stub_fields(vault_root: Path) -> None:
    cfg = config.load(vault_root)
    assert cfg.people_folder == "People"
    assert cfg.person_template == "Templates/person_template.md"


def test_load_omits_stub_fields_when_absent(vault_root: Path) -> None:
    (vault_root / "fam-circles.md").write_text(
        "# fam — circles\n\n```yaml\ncircles:\n"
        "  passive: {cadence_days: null, alert_threshold: null}\n```\n"
    )
    cfg = config.load(vault_root)
    assert cfg.people_folder is None
    assert cfg.person_template is None


def test_load_rejects_non_string_stub_fields(vault_root: Path) -> None:
    (vault_root / "fam-circles.md").write_text(
        "# fam — circles\n\n```yaml\ncircles: {}\npeople_folder: 42\n```\n"
    )
    with pytest.raises(config.ConfigError, match="people_folder"):
        config.load(vault_root)
