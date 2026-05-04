from __future__ import annotations

import tomllib
from pathlib import Path


def test_pyproject_exposes_fam_tend_console_script() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text())
    assert data["project"]["scripts"]["fam-tend"] == "scripts.fam_tend:main"
