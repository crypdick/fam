from __future__ import annotations

import json
import tomllib
from pathlib import Path


def test_pyproject_exposes_fam_tend_console_script() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text())
    assert data["project"]["scripts"]["fam-tend"] == "scripts.fam_tend:main"


def test_plugin_and_package_versions_match():
    version = tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]
    assert json.loads(Path(".claude-plugin/plugin.json").read_text())["version"] == version
    assert json.loads(Path(".codex-plugin/plugin.json").read_text())["version"] == version
    marketplace = json.loads(Path(".claude-plugin/marketplace.json").read_text())
    assert marketplace["plugins"][0]["version"] == version
