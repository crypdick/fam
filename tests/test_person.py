from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from scripts.lib import person


def test_discover_finds_at_prefix_files(vault_root: Path) -> None:
    paths = sorted(p.name for p in person.discover(vault_root))
    assert paths == ["@Alice.md", "@Bob.md", "@Carol.md", "@Dan.md", "@Eve.md"]


def test_load_alice(vault_root: Path) -> None:
    p = person.load(vault_root / "People" / "@Alice.md")
    assert p.name == "Alice"
    assert p.circle == "close"
    assert p.snooze_until is None
    assert p.next_action_at is None
    assert p.cadence_days_override is None
    assert p.contact_channels_ordered_preference == ["imessage", "email"]


def test_load_eve_has_snooze_until(vault_root: Path) -> None:
    p = person.load(vault_root / "People" / "@Eve.md")
    assert p.snooze_until == date(2030, 1, 1)


def test_load_missing_circle_raises(vault_root: Path) -> None:
    bad = vault_root / "People" / "@Mallory.md"
    bad.write_text("---\n---\n## Logged contacts\n")
    with pytest.raises(person.PersonSchemaError, match="circle"):
        person.load(bad)


def test_load_unknown_fam_field_raises(vault_root: Path) -> None:
    bad = vault_root / "People" / "@Mallory.md"
    bad.write_text("---\ncircle: close\nfam_typo_field: 1\n---\n")
    with pytest.raises(person.PersonSchemaError, match="unknown"):
        person.load(bad)


def test_user_namespace_passes_through(vault_root: Path) -> None:
    p = vault_root / "People" / "@Frank.md"
    p.write_text("---\ncircle: orbit\nprofession: dev\n---\n")
    loaded = person.load(p)
    assert loaded.extra["profession"] == "dev"


def test_write_roundtrips_extra_fields(tmp_path: Path) -> None:
    src = tmp_path / "@Foo.md"
    src.write_text(
        "---\ncircle: close\nprofession: dev\n---\n\n## Logged contacts\n- 2026-04-01 — hi\n"
    )
    p = person.load(src)
    person.write(p)
    text = src.read_text()
    assert "profession: dev" in text
    assert "circle: close" in text
    assert "## Logged contacts" in text
