"""fam-today: ranked "who to reach out to" queue."""

from __future__ import annotations

import argparse
import json as _json
import sys
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

from scripts.lib import config as config_mod
from scripts.lib import interactions, person, score, validate, vault


@dataclass(frozen=True)
class Row:
    name: str
    circle: str
    last_contacted: date | None
    days: int | None
    days_overdue: int | None
    score: float
    path: Path
    snoozed: bool


def compute_rows(
    *,
    today: date,
    include_below_threshold: bool,
    circle: str | None = None,
    include_snoozed: bool = False,
    limit: int | None = None,
) -> list[Row]:
    vault_root = vault.get_vault_root()
    with validate.guard(vault_root, default_missing_circle=True):
        cfg = config_mod.load(vault_root)
        rows: list[Row] = []
        for path in person.discover(vault_root):
            p = person.load_or_set_reference_circle(path)
            if circle is not None and p.circle != circle:
                continue
            if not p.periodic_contact_reminders and p.next_action_at is None:
                continue
            last = interactions.last_contacted(p)
            snoozed = bool(p.snooze_until and today < p.snooze_until)
            if snoozed and not include_snoozed:
                continue
            scored_person = replace(p, snooze_until=None) if include_snoozed else p
            s = score.score(scored_person, last=last, today=today, config=cfg)
            if not include_below_threshold and not score.in_queue(p, s, cfg):
                continue
            # Any no-cadence circle (for example reference/passive) stays out of the queue.
            if cfg.circles[p.circle].cadence_days is None:
                continue
            days = (today - last).days if last else None
            do = score.days_overdue(scored_person, last=last, today=today, config=cfg)
            rows.append(
                Row(
                    name=p.name,
                    circle=p.circle,
                    last_contacted=last,
                    days=days,
                    days_overdue=do,
                    score=s,
                    path=path.relative_to(vault_root),
                    snoozed=snoozed,
                )
            )
        # Highest score first, including +inf at the very top.
        rows = sorted(rows, key=lambda r: (-r.score, r.last_contacted or date.min))
        if limit is not None:
            rows = rows[:limit]
        return rows


def _format_table(rows: list[Row]) -> str:
    header = (
        f"{'SCORE':>6}  {'CIRCLE':<8}  {'LAST_CONTACTED':<14}"
        f"  {'DAYS':>4}  {'DAYS_OVERDUE':>12}  PATH"
    )
    out = [header]
    for r in rows:
        score_str = "inf" if r.score == float("inf") else f"{r.score:6.2f}"
        last_str = r.last_contacted.isoformat() if r.last_contacted else "-"
        days = str(r.days) if r.days is not None else "-"
        do = str(r.days_overdue) if r.days_overdue is not None else "-"
        out.append(f"{score_str:>6}  {r.circle:<8}  {last_str:<14}  {days:>4}  {do:>12}  {r.path}")
    return "\n".join(out)


def rows_as_dicts(rows: list[Row]) -> list[dict[str, Any]]:
    """Serialize queue rows for CLI and MCP, using valid JSON for infinite scores."""
    return [
        {
            "name": r.name,
            "circle": r.circle,
            "last_contacted": r.last_contacted.isoformat() if r.last_contacted else None,
            "days": r.days,
            "days_overdue": r.days_overdue,
            "score": ("inf" if r.score == float("inf") else r.score),
            "path": str(r.path),
            "snoozed": r.snoozed,
        }
        for r in rows
    ]


def _format_json(rows: list[Row]) -> str:
    return _json.dumps(rows_as_dicts(rows), indent=2, allow_nan=False)


def run(
    *,
    today: date,
    json_out: bool,
    include_below_threshold: bool = False,
    circle: str | None = None,
    include_snoozed: bool = False,
    limit: int | None = None,
) -> None:
    rows = compute_rows(
        today=today,
        include_below_threshold=include_below_threshold,
        circle=circle,
        include_snoozed=include_snoozed,
        limit=limit,
    )
    print(_format_json(rows) if json_out else _format_table(rows))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fam-today")
    parser.add_argument("--all", action="store_true", help="include below-threshold rows")
    parser.add_argument("--circle", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--include-snoozed", action="store_true")
    args = parser.parse_args(argv)
    try:
        run(
            today=date.today(),
            json_out=args.json,
            include_below_threshold=args.all,
            circle=args.circle,
            include_snoozed=args.include_snoozed,
            limit=args.limit,
        )
    except (config_mod.ConfigError, validate.ValidationError, vault.ObsidianCliError, OSError) as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
