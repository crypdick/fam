"""Preflight + postflight validators."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from scripts.lib import config as config_mod
from scripts.lib import person as person_mod


class ValidationError(RuntimeError):
    """Raised when preflight or postflight finds problems."""


@dataclass
class Report:
    ok: bool
    errors: list[str] = field(default_factory=list)


def preflight(vault_root: Path) -> Report:
    errors: list[str] = []
    try:
        config_mod.load(vault_root)
    except config_mod.ConfigError as e:
        errors.append(str(e))
    for path in person_mod.discover(vault_root):
        try:
            person_mod.load(path)
        except person_mod.PersonSchemaError as e:
            errors.append(str(e))
    return Report(ok=not errors, errors=errors)


@contextmanager
def guard(vault_root: Path) -> Iterator[None]:
    pre = preflight(vault_root)
    if not pre.ok:
        raise ValidationError("preflight failed:\n  " + "\n  ".join(pre.errors))
    yield
    post = preflight(vault_root)
    if not post.ok:
        raise ValidationError("postflight failed:\n  " + "\n  ".join(post.errors))
