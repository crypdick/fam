"""Preflight + postflight validators."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
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


def _inspect(
    vault_root: Path,
    *,
    targets: Sequence[Path] | None = None,
    allow_missing_circle: Path | None = None,
) -> tuple[Report, config_mod.Config | None, list[person_mod.Person]]:
    errors: list[str] = []
    cfg = None
    try:
        cfg = config_mod.load(vault_root)
    except config_mod.ConfigError as e:
        errors.append(str(e))
    people = []
    for path in person_mod.discover(vault_root) if targets is None else targets:
        try:
            loaded = person_mod.load(path, default_missing_circle=path == allow_missing_circle)
            if cfg is not None and loaded.circle not in cfg.circles:
                errors.append(f"{path}: circle {loaded.circle!r} is not configured in {cfg.path}")
            errors.extend(
                f"{path}: {error}" for error in interactions.logged_contact_errors(loaded.body)
            )
            people.append(loaded)
        except (person_mod.PersonSchemaError, OSError) as e:
            errors.append(str(e))
    return Report(ok=not errors, errors=errors), cfg, people


def preflight(
    vault_root: Path,
    *,
    targets: Sequence[Path] | None = None,
    allow_missing_circle: Path | None = None,
) -> Report:
    """Validate configuration and selected notes; None selects the whole vault."""
    report, _, _ = _inspect(
        vault_root, targets=targets, allow_missing_circle=allow_missing_circle
    )
    return report


def load_vault(vault_root: Path) -> tuple[config_mod.Config, list[person_mod.Person]]:
    """Load one validated population for a read operation, without rereading notes."""
    report, cfg, people = _inspect(vault_root)
    if not report.ok:
        raise ValidationError("preflight failed:\n  " + "\n  ".join(report.errors))
    assert cfg is not None  # A missing configuration produces a report error.
    return cfg, people


@contextmanager
def guard(
    vault_root: Path,
    *,
    targets: Sequence[Path] | None = None,
    allow_missing_circle: Path | None = None,
) -> Iterator[None]:
    """Check configuration and mutation targets before and after writing."""
    pre = preflight(vault_root, targets=targets, allow_missing_circle=allow_missing_circle)
    if not pre.ok:
        raise ValidationError("preflight failed:\n  " + "\n  ".join(pre.errors))
    try:
        yield
    finally:
        post = preflight(vault_root, targets=targets)
        if not post.ok:
            raise ValidationError("postflight failed:\n  " + "\n  ".join(post.errors))
