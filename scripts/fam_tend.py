"""Create person notes through Templater without inferring contact history."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from scripts.lib import config as config_mod
from scripts.lib import interactions, person, validate, vault

_WIKILINK_RE = re.compile(r"\[\[([^\]\n]+)\]\]")
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


@dataclass
class StubResult:
    """Outcome of the stub-creation pass."""

    created: list[str] = field(default_factory=list)
    retried: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    planned: list[str] = field(default_factory=list)


def _strip_markdown_code(text: str) -> str:
    """Exclude literal examples from wikilink scans."""
    text = "\n".join(line for _, line in interactions.markdown_lines(text))
    return _INLINE_CODE_RE.sub("", text)


def _stub_scan_name(raw_link: str) -> str | None:
    """Return an unresolved person-stub candidate from a raw wikilink.

    Only direct links like ``[[@Alice]]`` are treated as requests to create a
    person note. Path-prefixed links such as ``[[Z/@OpenAI]]`` may basename to
    an ``@`` note, but they point at another namespace and should not create a
    ``People/@OpenAI.md`` stub.
    """
    target = raw_link.split("|", 1)[0].split("#", 1)[0]
    if "/" in target or "\\" in target:
        return None
    if target.endswith(".md"):
        target = target[:-3]
    if not target.startswith("@"):
        return None
    if any(ch in target for ch in "*?"):
        return None
    if target == "@Name":
        return None
    return target


def _scan_at_wikilinks(vault_root: Path) -> set[str]:
    """Return the set of `@`-prefixed wikilink basenames mentioned anywhere in
    the vault. Skips dotfile dirs via `vault.iter_files`.
    """
    found: set[str] = set()
    for md in vault.iter_files(vault_root, "*.md"):
        try:
            text = _strip_markdown_code(vault.read_text(md, encoding="utf-8"))
        except OSError:
            continue
        for raw in _WIKILINK_RE.findall(text):
            base = _stub_scan_name(raw)
            if base is not None:
                found.add(base)
    return found


def _create_missing_stubs(
    vault_root: Path,
    cfg: config_mod.Config,
    *,
    person_name: str | None = None,
    dry_run: bool = False,
) -> StubResult:
    """Create requested or unresolved person notes, skipping existing names."""
    existing = {p.stem for p in person.discover(vault_root)}
    mentioned = {person_name} if person_name is not None else _scan_at_wikilinks(vault_root)
    unresolved = sorted(mentioned - existing)
    if not unresolved:
        return StubResult()
    if not cfg.people_folder or not cfg.person_template:
        raise config_mod.ConfigError(
            f"missing person notes found ({len(unresolved)}); set "
            "`people_folder` and `person_template` in fam-circles.md to "
            "enable template creation."
        )
    template = Path(cfg.person_template)
    folder = Path(cfg.people_folder)
    if dry_run:
        return StubResult(planned=unresolved)
    created: list[str] = []
    retried: list[str] = []
    failed: list[str] = []
    for name in unresolved:
        target = folder / f"{name}.md"
        try:
            attempts = vault.create_from_template(
                template=template, file=target, vault_root=vault_root
            )
            created.append(name)
            if attempts > 1:
                retried.append(name)
        except vault.ObsidianCliError as e:
            failed.append(f"{name}: {e}")
    return StubResult(created=created, retried=retried, failed=failed)


def tend(*, person_name: str | None = None, dry_run: bool = False) -> StubResult:
    if person_name is not None:
        name = person_name.strip().removeprefix("@")
        if not name or any(ch in name for ch in "/\\[]|#*?\r\n"):
            raise config_mod.ConfigError("--person must be a person name, not a path or wikilink")
        person_name = f"@{name}"
    vault_root = vault.get_vault_root()
    with validate.guard(vault_root):
        cfg = config_mod.load(vault_root)
        return _create_missing_stubs(vault_root, cfg, person_name=person_name, dry_run=dry_run)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fam-tend")
    parser.add_argument(
        "--person", help="ensure one named person note exists; skip vault link scan"
    )
    parser.add_argument("--dry-run", action="store_true", help="preview creation without writing")
    args = parser.parse_args(argv)
    try:
        stubs = tend(person_name=args.person, dry_run=args.dry_run)
    except (config_mod.ConfigError, validate.ValidationError, vault.ObsidianCliError, OSError) as e:
        print(str(e), file=sys.stderr)
        return 1
    for name in stubs.planned:
        print(f"would create stub: {name}")
    for name in stubs.created:
        marker = " (retried)" if name in stubs.retried else ""
        print(f"created stub: {name}{marker}")
    for failure in stubs.failed:
        print(f"WARNING: failed stub creation: {failure}", file=sys.stderr)
    return int(bool(stubs.failed))


if __name__ == "__main__":
    sys.exit(main())
