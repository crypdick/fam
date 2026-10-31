from __future__ import annotations

import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import frontmatter
import pytest

from scripts import fam_tend
from scripts.lib import vault


@pytest.fixture
def headless(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAM_CREATION_BACKEND", "obsidian-knowledge")


@pytest.fixture
def writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    executable = tmp_path / "bin" / "obsidian-knowledge"
    executable.parent.mkdir()
    executable.write_text(
        f"#!{sys.executable}\n"
        "import pathlib, sys\n"
        "target = pathlib.Path(sys.argv[sys.argv.index('--vault') + 1]) / sys.argv[-1]\n"
        "target.parent.mkdir(parents=True, exist_ok=True)\n"
        "with target.open('xb') as stream:\n"
        "    stream.write(sys.stdin.buffer.read())\n"
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(executable.parent))
    return executable


def test_ensure_headless_uses_exact_configured_template(
    headless, writer: Path, vault_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault_root))
    template = vault_root / "Templates/person_template.md"
    template.parent.mkdir()
    template.write_bytes(
        b"---\r\ncircle: needs-triage\r\ncustom: retained\r\n---\r\n\r\n## Logged contacts\r\n"
    )
    before = {p: p.read_bytes() for p in vault_root.rglob("*.md")}
    with patch("scripts.lib.vault.call", side_effect=AssertionError("desktop CLI called")):
        result = fam_tend.tend(person_name="Headless Person")
        again = fam_tend.tend(person_name="Headless Person")
    assert result.created == ["@Headless Person"]
    assert not result.failed
    assert again.created == []
    assert (vault_root / "People/@Headless Person.md").read_bytes() == template.read_bytes()
    assert {p: p.read_bytes() for p in before} == before


def test_headless_writer_refuses_existing_target(headless, writer: Path, tmp_path: Path) -> None:
    (tmp_path / "template.md").write_text("---\ncircle: needs-triage\n---\n")
    target = tmp_path / "@Existing.md"
    target.write_text("existing user content\n")
    with pytest.raises(vault.ObsidianCliError, match="FileExistsError"):
        vault.create_from_template(
            template=Path("template.md"), file=Path(target.name), vault_root=tmp_path
        )
    assert target.read_text() == "existing user content\n"


@pytest.mark.parametrize(
    "dynamic", ["<% tp.file.title %>", "<%* throw new Error('do not execute') %>", "{{title}}"]
)
def test_headless_rejects_dynamic_templates_before_writer(
    headless, writer: Path, tmp_path: Path, dynamic: str
) -> None:
    (tmp_path / "template.md").write_text(dynamic)
    with patch("scripts.lib.vault.subprocess.run") as run:
        with pytest.raises(vault.ObsidianCliError, match="dynamic.*template"):
            vault.create_from_template(
                template=Path("template.md"), file=Path("@Nope.md"), vault_root=tmp_path
            )
    run.assert_not_called()
    assert not (tmp_path / "@Nope.md").exists()


def test_headless_missing_writer_is_actionable_without_fallback(headless, tmp_path: Path) -> None:
    (tmp_path / "template.md").write_text("static note\n")
    with (
        patch("scripts.lib.vault.shutil.which", return_value=None),
        patch("scripts.lib.vault.call") as call,
    ):
        with pytest.raises(vault.ObsidianCliError, match="obsidian-knowledge.*PATH"):
            vault.create_from_template(
                template=Path("template.md"), file=Path("@Nope.md"), vault_root=tmp_path
            )
    call.assert_not_called()


def test_headless_preserves_permission_error_without_fallback(
    headless, writer: Path, tmp_path: Path
) -> None:
    writer.write_text(
        f"#!{sys.executable}\nimport sys\n"
        "sys.stderr.write('Permission denied: selected vault')\nsys.exit(1)\n"
    )
    (tmp_path / "template.md").write_text("static note\n")
    with patch("scripts.lib.vault.call") as call:
        with pytest.raises(vault.ObsidianCliError, match="Permission denied: selected vault"):
            vault.create_from_template(
                template=Path("template.md"), file=Path("@Nope.md"), vault_root=tmp_path
            )
    call.assert_not_called()
    assert not (tmp_path / "@Nope.md").exists()


def test_headless_rejects_case_distinct_parent(headless, writer: Path, tmp_path: Path) -> None:
    (tmp_path / "people").mkdir()
    (tmp_path / "template.md").write_text("static note\n")
    with pytest.raises(vault.ObsidianCliError, match="case-distinct"):
        vault.create_from_template(
            template=Path("template.md"), file=Path("People/@Nope.md"), vault_root=tmp_path
        )
    assert not (tmp_path / "People").exists()


def test_headless_requires_materialized_file(headless, writer: Path, tmp_path: Path) -> None:
    writer.write_text(f"#!{sys.executable}\n")
    (tmp_path / "template.md").write_text("static note\n")
    with pytest.raises(vault.ObsidianCliError, match="did not materialize"):
        vault.create_from_template(
            template=Path("template.md"), file=Path("@Nope.md"), vault_root=tmp_path
        )


def test_headless_missing_template_is_actionable(headless, writer: Path, tmp_path: Path) -> None:
    with pytest.raises(vault.ObsidianCliError, match="cannot read configured person template"):
        vault.create_from_template(
            template=Path("missing.md"), file=Path("@Nope.md"), vault_root=tmp_path
        )


@pytest.mark.parametrize(
    "template,target",
    [
        ("../escape.md", "@Nope.md"),
        ("template.md", "../@Nope.md"),
        ("template.md", "_sources/@Nope.md"),
    ],
)
def test_headless_rejects_unsafe_paths(
    headless, writer: Path, tmp_path: Path, template: str, target: str
) -> None:
    (tmp_path / "template.md").write_text("static note\n")
    with pytest.raises(vault.ObsidianCliError, match="vault|protected"):
        vault.create_from_template(template=Path(template), file=Path(target), vault_root=tmp_path)


@pytest.mark.integration
@pytest.mark.skipif(
    shutil.which("obsidian-knowledge") is None, reason="real verified writer not installed"
)
def test_real_headless_writer_applies_metadata_and_preserves_body(
    headless, vault_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = tmp_path / "settings/obsidian-knowledge"
    settings.mkdir(parents=True)
    (settings / "config.yaml").write_text(
        "note_creation:\n  template: Templates/creation-defaults.md\n"
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(settings.parent))
    (vault_root / "Templates").mkdir()
    (vault_root / "Templates/creation-defaults.md").write_text(
        '/* obsidian-knowledge:creation-defaults */ {"created":"fixture-created"};\n'
    )
    template = vault_root / "Templates/person_template.md"
    template.write_text(
        "---\ncircle: needs-triage\ncustom: preserved\n---\n\n"
        "## Logged contacts\n\n## Other references\n"
    )
    target = Path("People/@Metadata Person.md")
    assert (
        vault.create_from_template(
            template=Path("Templates/person_template.md"), file=target, vault_root=vault_root
        )
        == 1
    )
    saved = frontmatter.loads((vault_root / target).read_text())
    assert saved.metadata == {
        "created": "fixture-created",
        "circle": "needs-triage",
        "custom": "preserved",
    }
    assert saved.content == "## Logged contacts\n\n## Other references"
    before = (vault_root / target).read_bytes()
    with pytest.raises(vault.ObsidianCliError, match="already exists"):
        vault.create_from_template(
            template=Path("Templates/person_template.md"), file=target, vault_root=vault_root
        )
    assert (vault_root / target).read_bytes() == before
