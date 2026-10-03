"""Discover and parse `fam-circles.md`.

The file lives anywhere in the vault; uniqueness of its filename is the
discovery contract. Body holds a fenced ```yaml block with the circle
definitions.
"""

from __future__ import annotations

import math
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import vault as vault_mod
from .person import CIRCLES

CIRCLES_FILENAME = "fam-circles.md"
FAM_CIRCLES_PATH_ENV = "FAM_CIRCLES_PATH"
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
    configured_path = os.environ.get(FAM_CIRCLES_PATH_ENV)
    if configured_path:
        path = Path(configured_path).expanduser()
        if not path.is_absolute():
            path = vault_root / path
        try:
            mode = path.stat().st_mode
        except FileNotFoundError as e:
            raise ConfigError(
                f"{FAM_CIRCLES_PATH_ENV} points to missing {CIRCLES_FILENAME}: {path}"
            ) from e
        except OSError as e:
            raise ConfigError(
                f"{FAM_CIRCLES_PATH_ENV} points to unreadable {CIRCLES_FILENAME}: {path} "
                f"({type(e).__name__}: {e}). On macOS cron/uv may need Full Disk Access "
                f"or Documents permission."
            ) from e
        if not stat.S_ISREG(mode):
            raise ConfigError(
                f"{FAM_CIRCLES_PATH_ENV} points to missing {CIRCLES_FILENAME}: {path}"
            )
        if path.name != CIRCLES_FILENAME:
            raise ConfigError(
                f"{FAM_CIRCLES_PATH_ENV} must point to {CIRCLES_FILENAME}, got {path}"
            )
        return _parse(path)

    matches = sorted(vault_mod.iter_files(vault_root, CIRCLES_FILENAME))
    if not matches:
        raise ConfigError(
            f"{CIRCLES_FILENAME} not found anywhere under {vault_root}. "
            f"Create one with a ```yaml block defining circles."
        )
    if len(matches) > 1:
        joined = "\n  ".join(str(m) for m in matches)
        raise ConfigError(f"multiple {CIRCLES_FILENAME} found:\n  {joined}")
    return _parse(matches[0])


def _parse(path: Path) -> Config:
    try:
        text = vault_mod.read_text(path, encoding="utf-8")
    except OSError as e:
        raise ConfigError(f"{path}: unreadable config: {e}") from e
    block = _YAML_BLOCK_RE.search(text)
    if not block:
        raise ConfigError(f"no yaml code block in {path}")
    try:
        raw = yaml.safe_load(block.group(1))
    except yaml.YAMLError as e:
        raise ConfigError(f"yaml parse error in {path}: {e}") from e
    if not isinstance(raw, dict):
        raise ConfigError(f"config must be a YAML mapping in {path}")
    circles_raw = raw.get("circles")
    if not isinstance(circles_raw, dict) or not circles_raw:
        raise ConfigError(f"`circles` must be a nonempty mapping in {path}")
    circles: dict[str, CircleConfig] = {}
    for name, cfg in circles_raw.items():
        if name not in CIRCLES:
            raise ConfigError(f"{path}: unknown circle {name!r}; valid: {', '.join(CIRCLES)}")
        if not isinstance(cfg, dict) or not {"cadence_days", "alert_threshold"} <= cfg.keys():
            raise ConfigError(f"{path}: circle {name!r} requires cadence_days and alert_threshold")
        cadence = cfg["cadence_days"]
        threshold = cfg["alert_threshold"]
        if cadence is not None and (type(cadence) is not int or cadence <= 0):
            raise ConfigError(f"{path}: {name}.cadence_days must be int > 0 or null")
        if threshold is not None and (
            type(threshold) not in (int, float) or not math.isfinite(threshold)
        ):
            raise ConfigError(f"{path}: {name}.alert_threshold must be a finite number or null")
        if (cadence is None) != (threshold is None):
            raise ConfigError(
                f"{path}: {name} must set both cadence_days and alert_threshold or neither"
            )
        if name in {"reference", "passive"} and cadence is not None:
            raise ConfigError(f"{path}: {name} must have null cadence_days and alert_threshold")
        circles[name] = CircleConfig(cadence_days=cadence, alert_threshold=threshold)
    for required in ("reference", "passive"):
        if required not in circles:
            raise ConfigError(f"{path}: missing required circle {required!r}")
    people_folder = _relative_path(raw.get("people_folder"), "people_folder", path)
    person_template = _relative_path(raw.get("person_template"), "person_template", path)
    return Config(
        circles=circles,
        path=path,
        people_folder=people_folder,
        person_template=person_template,
    )


def _relative_path(value: object, field: str, path: Path) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"`{field}` must be a nonempty string in {path}")
    target = Path(value)
    if target.is_absolute() or ".." in target.parts or "\\" in value:
        raise ConfigError(f"`{field}` must be a vault-relative path in {path}")
    return target.as_posix()
