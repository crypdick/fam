"""Shared pytest fixtures."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "vault"


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    """Copy the read-only fixture vault into a tmp dir so tests can mutate it."""
    dest = tmp_path / "vault"
    shutil.copytree(FIXTURE_VAULT, dest)
    return dest
