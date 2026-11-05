from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path


def test_pyproject_exposes_one_fam_console_script() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text())
    assert data["project"]["scripts"] == {"fam": "scripts.cli:main"}


def test_generated_plugin_manifests_are_consistent():
    manifests = [
        json.loads(Path(name).read_text())
        for name in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json")
    ]
    marketplace = json.loads(Path(".claude-plugin/marketplace.json").read_text())
    manifests.append(next(plugin for plugin in marketplace["plugins"] if plugin["name"] == "fam"))
    for manifest in manifests:
        assert manifest["name"] == "fam"
        assert re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", manifest["version"])
    assert len({manifest["version"] for manifest in manifests}) == 1
