"""Discover and parse `fam-circles.md`.

The file lives anywhere in the vault; uniqueness of its filename is the
discovery contract. Body holds a fenced ```yaml block with the circle
definitions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import vault as vault_mod

CIRCLES_FILENAME = "fam-circles.md"
_YAML_BLOCK_RE = re.compile(r"```yaml\s*\n(.*?)```", re.DOTALL)


class ConfigError(RuntimeError):
    """Raised when fam-circles.md is missing, ambiguous, or unparseable."""


@dataclass(frozen=True)
class CircleConfig:
    cadence_days: int | None
    alert_threshold: float | None


@dataclass(frozen=True)
class Config:
    circles: dict[str, CircleConfig]
    path: Path
    people_folder: str | None = None
    person_template: str | None = None


def load(vault_root: Path) -> Config:
    matches = sorted(vault_mod.iter_files(vault_root, CIRCLES_FILENAME))
    if not matches:
        raise ConfigError(
            f"{CIRCLES_FILENAME} not found anywhere under {vault_root}. "
            f"Create one with a ```yaml block defining circles."
        )
    if len(matches) > 1:
        joined = "\n  ".join(str(m) for m in matches)
        raise ConfigError(f"multiple {CIRCLES_FILENAME} found:\n  {joined}")
    path = matches[0]
    text = path.read_text(encoding="utf-8")
    block = _YAML_BLOCK_RE.search(text)
    if not block:
        raise ConfigError(f"no yaml code block in {path}")
    try:
        raw = yaml.safe_load(block.group(1)) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"yaml parse error in {path}: {e}") from e
    circles_raw = raw.get("circles") or {}
    if not isinstance(circles_raw, dict):
        raise ConfigError(f"`circles` must be a mapping in {path}")
    circles = {
        name: CircleConfig(
            cadence_days=cfg.get("cadence_days"),
            alert_threshold=cfg.get("alert_threshold"),
        )
        for name, cfg in circles_raw.items()
    }
    people_folder = raw.get("people_folder")
    if people_folder is not None and not isinstance(people_folder, str):
        raise ConfigError(f"`people_folder` must be a string in {path}")
    person_template = raw.get("person_template")
    if person_template is not None and not isinstance(person_template, str):
        raise ConfigError(f"`person_template` must be a string in {path}")
    return Config(
        circles=circles,
        path=path,
        people_folder=people_folder,
        person_template=person_template,
    )
