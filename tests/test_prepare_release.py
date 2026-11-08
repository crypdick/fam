"""Exercise release preparation through its CLI in real Git repositories."""

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "prepare_release.py"


@pytest.fixture
def release_repo(tmp_path, monkeypatch):
    for key in os.environ:
        if key.startswith("GIT_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "output"))
    git(tmp_path, "init", "--quiet", "-b", "main")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", "test@example.com")
    (tmp_path / ".gitignore").write_text("output\n", encoding="utf-8")
    write_versions(tmp_path, "1.5.5")
    return tmp_path


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],  # noqa: S607 -- Git is a required development tool resolved through PATH.
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def commit(root: Path, message: str) -> str:
    git(root, "add", ".")
    git(root, "commit", "--quiet", "--no-verify", "--allow-empty", "-m", message)
    return git(root, "rev-parse", "HEAD")


def write_versions(root: Path, version: str) -> None:
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "fam"\nversion = "{version}"\ndependencies = []\n', encoding="utf-8"
    )
    for name in (
        ".claude-plugin/plugin.json",
        ".codex-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
    ):
        path = root / name
        path.parent.mkdir(exist_ok=True)
        value = (
            {
                "plugins": [
                    {"name": "other", "version": "9.0.0"},
                    {"name": "fam", "version": version},
                ]
            }
            if "marketplace" in name
            else {"name": "fam", "version": version, "description": "Keep this"}
        )
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def run_release(root: Path, source: str, previous: str) -> subprocess.CompletedProcess[str]:
    (root / "output").unlink(missing_ok=True)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--source", source, "--previous", previous],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def assert_versions(root: Path, expected: str) -> None:
    assert tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"] == expected
    for name in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        value = json.loads((root / name).read_text())
        assert value == {"name": "fam", "version": expected, "description": "Keep this"}
    marketplace = json.loads((root / ".claude-plugin/marketplace.json").read_text())
    assert marketplace["plugins"] == [
        {"name": "other", "version": "9.0.0"},
        {"name": "fam", "version": expected},
    ]


def test_unchanged_version_gets_patch_bump(release_repo):
    previous = commit(release_repo, "base")
    source = commit(release_repo, "feature")

    result = run_release(release_repo, source, previous)

    assert result.returncode == 0, result.stderr
    assert_versions(release_repo, "1.5.6")
    assert (release_repo / "output").read_text() == "state=new\nversion=1.5.6\n"


def test_manual_bump_in_earlier_push_commit_is_preserved_and_synced(release_repo):
    previous = commit(release_repo, "base")
    project = release_repo / "pyproject.toml"
    project.write_text(project.read_text().replace('"1.5.5"', '"1.6.0"'))
    commit(release_repo, "manual minor release")
    source = commit(release_repo, "another change in same push")

    result = run_release(release_repo, source, previous)

    assert result.returncode == 0, result.stderr
    assert_versions(release_repo, "1.6.0")


def test_uv_package_only_bump_passes_checkout_checks_and_syncs_at_release(release_repo):
    project = release_repo / "pyproject.toml"
    project.write_text(project.read_text() + '\n[project.scripts]\nfam = "scripts.cli:main"\n')
    metadata_tests = release_repo / "tests" / "test_project_metadata.py"
    metadata_tests.parent.mkdir()
    metadata_tests.write_bytes((SCRIPT.parents[1] / "tests" / metadata_tests.name).read_bytes())
    subprocess.run(
        ["uv", "lock", "--offline", "--python", sys.executable],
        cwd=release_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    previous = commit(release_repo, "base")
    subprocess.run(
        ["uv", "version", "--bump", "minor", "--no-sync", "--offline"],
        cwd=release_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    assert (
        json.loads((release_repo / ".claude-plugin/plugin.json").read_text())["version"] == "1.5.5"
    )
    lock = tomllib.loads((release_repo / "uv.lock").read_text())
    assert next(item["version"] for item in lock["package"] if item["name"] == "fam") == "1.6.0"

    quality = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_project_metadata.py", "-q"],
        cwd=release_repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert quality.returncode == 0, quality.stdout + quality.stderr
    source = commit(release_repo, "package-only minor release")
    result = run_release(release_repo, source, previous)
    assert result.returncode == 0, result.stderr
    assert_versions(release_repo, "1.6.0")


def test_codex_build_suffix_is_synced_to_release_version(release_repo):
    previous = commit(release_repo, "base")
    path = release_repo / ".codex-plugin/plugin.json"
    path.write_text(path.read_text().replace('"1.5.5"', '"1.5.5+codex.20261021175844"'))
    source = commit(release_repo, "feature")

    result = run_release(release_repo, source, previous)

    assert result.returncode == 0, result.stderr
    assert_versions(release_repo, "1.5.6")


def test_retry_does_not_bump_again(release_repo):
    previous = commit(release_repo, "base")
    source = commit(release_repo, "feature")
    assert run_release(release_repo, source, previous).returncode == 0
    commit(release_repo, f"Release 1.5.6\n\nSource-Commit: {source}")

    result = run_release(release_repo, source, previous)

    assert result.returncode == 0, result.stderr
    assert_versions(release_repo, "1.5.6")
    assert (release_repo / "output").read_text() == "state=retry\nversion=1.5.6\n"
    assert git(release_repo, "status", "--porcelain") == ""


def test_superseded_run_does_not_touch_files(release_repo):
    previous = commit(release_repo, "base")
    source = commit(release_repo, "feature")
    commit(release_repo, "superseding push")

    result = run_release(release_repo, source, previous)

    assert result.returncode == 0, result.stderr
    assert_versions(release_repo, "1.5.5")
    assert (release_repo / "output").read_text() == "state=stale\nversion=1.5.5\n"
    assert git(release_repo, "status", "--porcelain") == ""


@pytest.mark.parametrize("version", ["1.4.0", "invalid", "1.6.0rc1"])
def test_invalid_or_decreased_version_fails_without_writes(release_repo, version):
    previous = commit(release_repo, "base")
    write_versions(release_repo, version)
    source = commit(release_repo, "bad version")

    result = run_release(release_repo, source, previous)

    assert result.returncode != 0
    assert "version decreased" in result.stderr or "major.minor.patch" in result.stderr
    assert git(release_repo, "status", "--porcelain") == ""
    assert not (release_repo / "output").exists()


@pytest.mark.parametrize("argument", ["source", "previous"])
def test_invalid_sha_is_rejected(release_repo, argument):
    source = commit(release_repo, "base")
    result = run_release(
        release_repo,
        "HEAD" if argument == "source" else source,
        "HEAD" if argument == "previous" else source,
    )

    assert result.returncode != 0
    assert "full Git commit SHA" in result.stderr
    assert git(release_repo, "status", "--porcelain") == ""


def test_missing_marketplace_entry_fails_without_partial_writes(release_repo):
    previous = commit(release_repo, "base")
    (release_repo / ".claude-plugin/marketplace.json").write_text('{"plugins": []}\n')
    source = commit(release_repo, "bad marketplace")

    result = run_release(release_repo, source, previous)

    assert result.returncode != 0
    assert "must register fam" in result.stderr
    assert git(release_repo, "status", "--porcelain") == ""


@pytest.mark.parametrize(
    ("name", "content", "error"),
    [
        (".claude-plugin/plugin.json", "[]\n", "must contain a JSON object"),
        (".claude-plugin/marketplace.json", '{"plugins": {}}\n', "must contain a plugins array"),
        ("pyproject.toml", "[project]\nversion = '1.5.5'\n", "must declare version"),
    ],
)
def test_malformed_release_metadata_fails_without_partial_writes(
    release_repo, name, content, error
):
    previous = commit(release_repo, "base")
    (release_repo / name).write_text(content)
    source = commit(release_repo, "malformed metadata")

    result = run_release(release_repo, source, previous)

    assert result.returncode != 0
    assert error in result.stderr
    assert git(release_repo, "status", "--porcelain") == ""


@pytest.mark.parametrize(
    "manifest",
    [".claude-plugin/plugin.json", ".codex-plugin/plugin.json", ".claude-plugin/marketplace.json"],
)
def test_manifest_identity_fails_before_writing(release_repo, manifest):
    previous = commit(release_repo, "base")
    path = release_repo / manifest
    value = json.loads(path.read_text())
    if "marketplace" in manifest:
        value["plugins"].append({"name": "fam", "version": "1.5.5"})
    else:
        value["name"] = "wrong-plugin"
    path.write_text(json.dumps(value))
    source = commit(release_repo, "invalid identity")

    result = run_release(release_repo, source, previous)

    assert result.returncode != 0
    assert "fam" in result.stderr
    assert git(release_repo, "status", "--porcelain") == ""
