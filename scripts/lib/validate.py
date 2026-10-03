"""Preflight + postflight validators."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from scripts.lib import config as config_mod
from scripts.lib import interactions
from scripts.lib import person as person_mod


class ValidationError(RuntimeError):
    """Raised when preflight or postflight finds problems."""


@dataclass
class Report:
    ok: bool
    errors: list[str] = field(default_factory=list)


def preflight(vault_root: Path, *, default_missing_circle: bool = False) -> Report:
    errors: list[str] = []
    cfg = None
    try:
        cfg = config_mod.load(vault_root)
    except config_mod.ConfigError as e:
        errors.append(str(e))
    for path in person_mod.discover(vault_root):
        try:
            loaded = person_mod.load(path, default_missing_circle=default_missing_circle)
            if cfg is not None and loaded.circle not in cfg.circles:
                errors.append(f"{path}: circle {loaded.circle!r} is not configured in {cfg.path}")
            errors.extend(
                f"{path}: {error}" for error in interactions.logged_contact_errors(loaded.body)
            )
        except (person_mod.PersonSchemaError, OSError) as e:
            errors.append(str(e))
    return Report(ok=not errors, errors=errors)


@contextmanager
def guard(vault_root: Path, *, default_missing_circle: bool = False) -> Iterator[None]:
    pre = preflight(vault_root, default_missing_circle=default_missing_circle)
    if not pre.ok:
        raise ValidationError("preflight failed:\n  " + "\n  ".join(pre.errors))
    try:
        yield
    finally:
        post = preflight(vault_root)
        if not post.ok:
            raise ValidationError("postflight failed:\n  " + "\n  ".join(post.errors))
